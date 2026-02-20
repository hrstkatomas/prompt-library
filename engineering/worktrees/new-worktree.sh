#!/bin/bash

BRANCH_NAME=$1
MAIN_REPO=$(git rev-parse --show-toplevel)
WORKTREE_PATH="../worktrees/$BRANCH_NAME"

if [ -z "$BRANCH_NAME" ]; then
  echo "Usage: ./new-worktree.sh <branch-name>"
  exit 1
fi

# Create the worktree
git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"

# Symlink shared dependencies
ln -s "$MAIN_REPO/node_modules" "$WORKTREE_PATH/node_modules"
ln -s "$MAIN_REPO/vendor" "$WORKTREE_PATH/vendor"

# Copy .idea config so editor doesn't re-index from scratch
cp -r "$MAIN_REPO/.idea" "$WORKTREE_PATH/.idea"
echo "$BRANCH_NAME" > "$WORKTREE_PATH/.idea/name"

echo "✓ Worktree ready at $WORKTREE_PATH"