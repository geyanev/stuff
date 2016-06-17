#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

echo "PowerUP this account with neccessary development tools"

script_path=$(readlink -f $0)
cd $script_path

echo "Bash"
git clone https://github.com/chriskempson/base16-shell.git ~/.config/base16-shell

cat >> ~/.bashrc <<'EOF'
# Base16 Shell
BASE16_SHELL="$HOME/.config/base16-shell/base16-default.dark.sh"
[[ -s $BASE16_SHELL ]] && source $BASE16_SHELL
EOF

echo "Vim"
ln -s vimrc ~/.vimrc
curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
	    https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

echo "Tmux"
ln -s tmux.conf ~/.tmux.conf
