#!/bin/bash

REMOTE_HOST="dev-dsk-kylhouns-2a-4d6ae854.us-west-2.amazon.com"
LOCAL_DIR="/Users/kylhouns/code/osd/agentops"
REMOTE_DIR="/home/kylhouns/code/agentops"

sync_once() {
  rsync -avz --delete \
    --filter=':- .gitignore' \
    --exclude='.git' \
    --exclude='.kiro' \
    -e ssh \
    "$LOCAL_DIR/" \
    "$REMOTE_HOST:$REMOTE_DIR"
}

if [ "$1" = "--once" ]; then
  sync_once
else
  if ! command -v fswatch &> /dev/null; then
    echo "fswatch not found. Install with: brew install fswatch"
    exit 1
  fi
  echo "Starting continuous sync..."
  sync_once
  fswatch -o "$LOCAL_DIR" | while read; do
    echo "Changes detected, syncing..."
    sync_once
  done
fi
