#!/bin/bash

echo "Install Ansible"
pip install ansible

echo "Run Ansible"
ansible-playbook -i ,127.0.0.1 os_powerup.yml
echo "setup git PROMPT"
cd ~
git clone https://github.com/magicmonty/bash-git-prompt.git .bash-git-prompt --depth=1

cat >> .bashrc <<'EOF'

source ~/.bash-git-prompt/gitprompt.sh
GIT_PROMPT_ONLY_IN_REPO=1
EOF

echo "git bash completion"
curl http://git.io/vfhol > ~/.git-completion.bash && echo '[ -f ~/.git-completion.bash ] && . ~/.git-completion.bash' >> ~/.bashrc
