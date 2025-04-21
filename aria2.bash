#!/bin/bash

# Run aria2c with the specified options
aria2c --enable-rpc \
       --rpc-listen-all=true \
       --rpc-allow-origin-all \
       --http-no-cache \
       --allow-overwrite