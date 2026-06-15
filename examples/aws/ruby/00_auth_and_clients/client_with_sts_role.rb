require 'aws-sdk-bedrockruntime'
require 'aws-sdk-sts'
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
# Lasso AWS Bedrock Converse example using STS AssumeRole.
#
# This example sends Bedrock Runtime requests to the Lasso proxy. Lasso then
# forwards the request to Amazon Bedrock.
#
# Auth flow:
#   1. The app uses local AWS credentials to call STS AssumeRole.
#   2. STS returns temporary role credentials.
#   3. The AWS SDK signs the Bedrock request with those temporary credentials.
#   4. A small SDK plugin adds the Lasso API key header.
#   5. Lasso receives the signed Bedrock request and forwards it to AWS.
#
# Required .env values:
#   AWS_REGION
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   AWS_ROLE_ARN
#   BEDROCK_TEXT_MODEL_ID
#   LASSO_PROXY_ENDPOINT
#   LASSO_X_API_KEY
#
# Optional .env values:
#   AWS_SESSION_TOKEN
#   AWS_ROLE_SESSION_NAME
#   AWS_EXTERNAL_ID
#   DISABLE_SSL_VERIFICATION=true
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 1. Load configuration
# -----------------------------------------------------------------------------

env_path = File.expand_path('../../../.env', __dir__)

raise "Missing .env file at #{env_path}" unless File.exist?(env_path)

Dotenv.load(env_path)

region = ENV.fetch('AWS_REGION', 'us-east-1')

source_access_key = require_env('AWS_ACCESS_KEY_ID')
source_secret_key = require_env('AWS_SECRET_ACCESS_KEY')
source_session_token = ENV['AWS_SESSION_TOKEN']

role_arn = require_env('AWS_ROLE_ARN')
role_session_name = ENV.fetch('AWS_ROLE_SESSION_NAME', 'lasso-ruby-bedrock-example')
external_id = ENV['AWS_EXTERNAL_ID']

model_id = require_env('BEDROCK_TEXT_MODEL_ID')
lasso_api_key = require_env('LASSO_X_API_KEY')
lasso_proxy_url = require_env('LASSO_PROXY_ENDPOINT').delete_suffix('/')

# The AWS SDK sends Bedrock Runtime requests to Lasso instead of AWS directly.
lasso_endpoint = "#{lasso_proxy_url}/v1/bedrock"

# -----------------------------------------------------------------------------
# 2. Assume the AWS role with STS
# -----------------------------------------------------------------------------

source_credentials = Aws::Credentials.new(
  source_access_key,
  source_secret_key,
  source_session_token
)

sts_client = Aws::STS::Client.new(
  region: region,
  credentials: source_credentials,
  ssl_verify_peer: !disable_ssl_verification?
)

assume_role_params = {
  role_arn: role_arn,
  role_session_name: role_session_name
}

# Use ExternalId when the target role trust policy requires it.
assume_role_params[:external_id] = external_id if external_id && !external_id.strip.empty?

assumed_role = sts_client.assume_role(assume_role_params)

role_credentials = Aws::Credentials.new(
  assumed_role.credentials.access_key_id,
  assumed_role.credentials.secret_access_key,
  assumed_role.credentials.session_token
)

# -----------------------------------------------------------------------------
# 3. Add the Lasso API key to each Bedrock request
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
# 4. Create the Bedrock Runtime client through Lasso
# -----------------------------------------------------------------------------

client = Aws::BedrockRuntime::Client.new(
  region: region,
  endpoint: lasso_endpoint,

  # These are the temporary credentials returned by STS AssumeRole.
  credentials: role_credentials,

  lasso_api_key: lasso_api_key,

  # Local testing only.
  # Do not disable certificate validation in production.
  ssl_verify_peer: !disable_ssl_verification?
)

# -----------------------------------------------------------------------------
# 5. Send a Bedrock Converse request
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
# 6. Print response
# -----------------------------------------------------------------------------

puts "HTTP status code: #{response.context.http_response.status_code}"

answer = response.to_h.dig(:output, :message, :content, 0, :text)

puts
puts 'Answer:'
puts answer
