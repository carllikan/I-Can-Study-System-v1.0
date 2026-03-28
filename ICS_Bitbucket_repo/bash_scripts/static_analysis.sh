#!/bin/bash

if [ -L $0 ] ; then
    ME=$(readlink $0)
else
    ME=$0
fi
SCRIPT_DIR=$(dirname $ME)

LOCATE_FILE=`which prospector`
if [ "" == "$LOCATE_FILE" ]; then
    pip install prospector
else
    echo prospector already installed
fi

LOCATE_FILE=`which bandit`
if [ "" == "$LOCATE_FILE" ]; then
    pip install bandit
else
    echo bandit already installed
fi

LOCATE_FILE=`which npm`
if [ "" == "$LOCATE_FILE" ]; then
    yum install -y node
else
    echo node and npm already installed
fi

LOCATE_FILE=`which jscpd`
if [ "" == "$LOCATE_FILE" ]; then
    npm install -g jscpd
else
    echo jscpd already installed
fi

CWD=`pwd`

PYDIRS=`cd $SCRIPT_DIR/..;find . -name "*.py" -exec dirname {} \; | sort -u`

for pydir in $PYDIRS; do
    cd $SCRIPT_DIR/../$pydir
    echo -----------------------------------------------------------
    echo `pwd`
    echo ------------------- prospector ----------------------------
    prospector | grep -v "pylint: import-error"
    echo ------------------- bandit --------------------------------
    bandit *.py
    cd $CWD
done

echo ------------------- jscpd ---------------------------------
cd $SCRIPT_DIR/..
jscpd --max-lines=10000 --max-size=10000kb $PYDIRS
cd $CWD


