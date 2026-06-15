require 'aws-sdk-bedrockruntime'
require 'dotenv'
require 'json'

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def require_env(name)
  value = ENV[name]

  raise "Missing required environment variable: #{name}" if value.nil? || value.strip.empty?

  value
end

def disable_ssl_verification?
  ENV['DISABLE_SSL_VERIFICATION'].to_s.casecmp('true').zero?
end

# -----------------------------------------------------------------------------
# Lasso AWS Bedrock Converse example using an AWS profile.
#
# This example sends Bedrock Runtime requests to the Lasso proxy. Lasso then
# forwards the request to Amazon Bedrock.
#
# Auth flow:
#   1. The AWS SDK loads credentials from the configured AWS profile.
#   2. The AWS SDK signs the Bedrock request with those profile credentials.
#   3. A small SDK plugin adds the Lasso API key header.
#   4. Lasso receives the signed Bedrock request and forwards it to AWS.
#
# Required .env values:
#   AWS_REGION
#   AWS_PROFILE
#   BEDROCK_TEXT_MODEL_ID
#   LASSO_PROXY_ENDPOINT
#   LASSO_X_API_KEY
#
# Optional .env value:
#   DISABLE_SSL_VERIFICATION=true
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 1. Load configuration
# -----------------------------------------------------------------------------

env_path = File.expand_path('../../../.env', __dir__)

raise "Missing .env file at #{env_path}" unless File.exist?(env_path)

Dotenv.load(env_path)

region = ENV.fetch('AWS_REGION', 'us-east-1')
profile_name = require_env('AWS_PROFILE')

model_id = require_env('BEDROCK_TEXT_MODEL_ID')
lasso_api_key = require_env('LASSO_X_API_KEY')
lasso_proxy_url = require_env('LASSO_PROXY_ENDPOINT').delete_suffix('/')

# The AWS SDK sends Bedrock Runtime requests to Lasso instead of AWS directly.
lasso_endpoint = "#{lasso_proxy_url}/v1/bedrock"

# -----------------------------------------------------------------------------
# 2. Add the Lasso API key to each Bedrock request
# -----------------------------------------------------------------------------

# The AWS SDK signs the request. This plugin only adds the Lasso API key header.
class LassoHeaderPlugin < Seahorse::Client::Plugin
  option(:lasso_api_key)

  class Handler < Seahorse::Client::Handler
    def call(context)
      context.http_request.headers['lasso-x-api-key'] =
        context.config.lasso_api_key

      @handler.call(context)
    end
  end

  handler(Handler, step: :build)
end

Aws::BedrockRuntime::Client.add_plugin(LassoHeaderPlugin)

# -----------------------------------------------------------------------------
# 3. Create the Bedrock Runtime client through Lasso
# -----------------------------------------------------------------------------

client = Aws::BedrockRuntime::Client.new(
  region: region,
  endpoint: lasso_endpoint,

  # The SDK loads credentials from ~/.aws/credentials and ~/.aws/config.
  profile: profile_name,

  lasso_api_key: lasso_api_key,

  # Local testing only.
  # Do not disable certificate validation in production.
  ssl_verify_peer: !disable_ssl_verification?
)

# -----------------------------------------------------------------------------
# 4. Send a Bedrock Converse request
# -----------------------------------------------------------------------------

response = client.converse(
  model_id: model_id,
  messages: [
    {
      role: 'user',
      content: [
        {
          text: 'In a single word, what is the answer to the great question of life, the universe and everything?'
        }
      ]
    }
  ],
  inference_config: {
    max_tokens: 512
  }
)

# -----------------------------------------------------------------------------
# 5. Print response
# -----------------------------------------------------------------------------

puts "HTTP status code: #{response.context.http_response.status_code}"

answer = response.to_h.dig(:output, :message, :content, 0, :text)

puts
puts 'Answer:'
puts answer
