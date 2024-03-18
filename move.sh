#!/bin/bash
#
move_safely() {
    local src=$1
    local dst=$(echo $src | tr ":#" "__")

    if [[ -d $src && ! -e $dst ]]; then
        mv "$src" "$dst"
    elif [[ -f $src ]]; then
        mv "$src" "$dst"
    fi
}

export -f move_safely

find . -depth -type d -name "*[:#]*" -exec bash -c 'move_safely "$0"' {} \;
find . -depth -type f -name "*[:#]*" -exec bash -c 'move_safely "$0"' {} \;
