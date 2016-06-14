#!/bin/bash

set -o errexit
set -o nounset
set -o pipefail

echo "PowerUP this account with neccessary development tools"

script_path=$(readlink -f $0)
cd $script_path

echo "Vim"
ln -s vimrc ~/.vimrc
curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
	    https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

echo "Tmux"
ln -s tmux.conf ~/.tmux.conf
