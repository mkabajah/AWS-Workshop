# Lab 09 · Point this terminal at AWS Emulator (macOS and Linux).
#
#   source labs/09-aws-emulator/emulator-env.sh          # port 9297
#   source labs/09-aws-emulator/emulator-env.sh 9298     # a second emulator
#
# Undo it by closing the terminal. Nothing here touches your real AWS settings files.

PORT="${1:-9297}"
E="$HOME/.aws/emulator/$PORT"

export AWS_ENDPOINT_URL="https://127.0.0.1:$PORT"   # 127.0.0.1, not localhost (S3 bucket names)
export AWS_SHARED_CREDENTIALS_FILE="$E/emulator_credentials"
export AWS_CONFIG_FILE="$E/config"
export AWS_CA_BUNDLE="$E/ca.pem"                      # the emulator's own HTTPS certificate
export AWS_EC2_METADATA_DISABLED=true
export AWS_DISABLE_HOST_PREFIX_INJECTION=true
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1

# Make sure real credentials can't be used by accident.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE

if [ ! -f "$E/emulator_credentials" ]; then
  echo "Warning: $E/emulator_credentials not found. Is the emulator running on port $PORT?"
fi
echo "This terminal now talks to AWS Emulator at $AWS_ENDPOINT_URL"
echo "Check:  aws sts get-caller-identity   (Account must be 000000000000)"
