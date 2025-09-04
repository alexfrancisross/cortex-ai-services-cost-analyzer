#!/bin/bash

# Claude Code AWS Bedrock Setup Script
# This script configures environment variables and starts Claude Code with AWS Bedrock

set -e  # Exit on any error

echo "🚀 Starting Claude Code with AWS Bedrock..."
echo "📍 Region: us-west-2"
echo "🤖 Primary Model: Claude Sonnet 4"
echo "⚡ Fast Model: Claude 3.5 Haiku"
echo ""

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &>/dev/null; then
    echo "❌ Error: AWS credentials not configured or expired"
    echo "Please run 'aws configure' first or refresh your credentials"
    exit 1
fi

echo "✅ AWS credentials verified"

# Set AWS region
export AWS_REGION=us-west-2
export AWS_DEFAULT_REGION=us-west-2

# Enable Claude Code Bedrock integration
export CLAUDE_CODE_USE_BEDROCK=1

# Configure Claude models using inference profile IDs
export ANTHROPIC_MODEL=us.anthropic.claude-sonnet-4-20250514-v1:0
export ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-3-5-haiku-20241022-v1:0

# Set recommended token limits for Bedrock
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=4096
export MAX_THINKING_TOKENS=1024

# Optional: Set AWS output format
export AWS_DEFAULT_OUTPUT=json

echo "✅ Environment variables configured"
echo ""

# Display current configuration
echo "📋 Current Configuration:"
echo "   AWS Region: $AWS_REGION"
echo "   Primary Model: $ANTHROPIC_MODEL"
echo "   Fast Model: $ANTHROPIC_SMALL_FAST_MODEL"
echo "   Bedrock Enabled: $CLAUDE_CODE_USE_BEDROCK"
echo "   Max Output Tokens: $CLAUDE_CODE_MAX_OUTPUT_TOKENS"
echo "   Max Thinking Tokens: $MAX_THINKING_TOKENS"
echo ""

# Check if claude command exists
if ! command -v claude &>/dev/null; then
    echo "❌ Error: 'claude' command not found"
    echo "Please install Claude Code first: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

echo "🎯 Starting Claude Code..."
echo "   (Press Ctrl+C to exit)"
echo ""

# Start Claude Code
claude "$@"