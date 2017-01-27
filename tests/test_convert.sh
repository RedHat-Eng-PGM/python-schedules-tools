#!/usr/bin/env bash

BIN_CONVERT=${1:-schedule_converter.py}
BIN_DIFF=${2:-schedule_diff.py}
CAN_RUN=1

if ! [ -x $BIN_CONVERT ]; then
    echo "Converter $BIN_CONVERT is not executable"
    CAN_RUN=0
fi

if ! [ -x $BIN_CONVERT ]; then
    echo "Schedule diff $BIN_CONVERT is not executable"
    CAN_RUN=0
fi

if [[ "$CAN_RUN" != "1" ]]; then
    echo "Usage:"
    echo -e "\t$0 [converter-bin] [diff-bin]"
    exit 1
fi

function test_combination() {
    IN=$1; shift
    FORMAT=$1; shift
    OUT=$1; shift
    ARGS=$1; shift

    echo "----------------------------------------------------"
    # wipe out previous content
    echo -n > $OUT

    $BIN_CONVERT $ARGS $IN $FORMAT $OUT

    $BIN_DIFF --whole-days $IN $OUT

    if [[ "$?" == "0" ]]; then
        echo -e "PASSED \t$IN ... $OUT"
    else
        echo -e "FAILED!\t$IN ... $OUT"
    fi
}

function run_tests() {
    OUT=$(mktemp)

    TJX='data/schedule.tjx'
    TJX2='data/schedule-v2.tjx'
    SMARTSHEET='data/smartsheet.xml'
    OUT=${OUT}.tjx

    # TJX - TJX
    test_combination $TJX 'tjx' $OUT

    # TJX2 - TJX
    test_combination $TJX2 'tjx' $OUT

    # MSP - TJX
    test_combination $SMARTSHEET 'tjx' $OUT '--tj-id someid --major 10 --minor 0 --maint 42'

    # cleanup
    rm $OUT
}

run_tests
