#!/bin/bash

# UPDATE this list of git repos that you want to sync
repositories=(
  "git@gitlab.com:....REPO1.git"
  "git@gitlab.com:....REPO2.git"
  "git@gitlab.com:....REPO3.git"
)

# UPDATE this private key location, so cron schedule can have permission for SSH
export GIT_SSH_COMMAND="ssh -i /home/USER/.ssh/id_rsa"



formatted_date_time=$(date +"%Y-%m-%d %H:%M:%S")
echo "----- git-refresh.sh ----"
echo "$formatted_date_time"

for repo in "${repositories[@]}"; do
  # Extract the repository name from the URL
  repo_name=$(basename "$repo" .git)
  
  if [ -d "$repo_name" ]; then
    # The repository already exists, pull the latest changes
    echo "Pulling latest changes for $repo_name..."
    cd "$repo_name" || exit
    git reset --hard origin/master
    git pull
    cd ..
  else
    # The repository is missing, clone it
    echo "Cloning $repo_name..."
    git clone "$repo" 
  fi
done
