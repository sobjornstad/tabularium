#!/bin/bash

from='designer'
into='ui/forms'
packageInit='ui/forms/__init__.py'

if [ ! -d "$from" ]; then
    echo "This script must be run from the project's root directory."
    exit
fi

mkdir -p "$into"

cat <<PACKAGEINIT > "$packageInit"
# -*- coding: utf-8 -*-
# This file is automatically generated by designer/makeForms.sh.
# *** Any changes made in this file will be lost! ***

PACKAGEINIT

didUpdate=0
for i in "$from/"*.ui
do
    moduleName="$(basename "$i" .ui)"
    if [ "$i" -nt "$into/$moduleName.py" ]; then
        didUpdate=1
        echo "Updating: $moduleName"
        pyuic4 "$i" -o "$into/$moduleName.py"
    fi
    echo "from . import $moduleName" >> "$packageInit"
done

if [ $didUpdate != 1 ]; then
    echo "No forms to update."
fi
