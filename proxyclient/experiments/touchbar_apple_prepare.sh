#!/bin/bash

if [ ! -f bad_apple.webm ] ; then
    yt-dlp -o bad_apple 'https://www.youtube.com/watch?v=UkgK8eUdpAo'
fi

ffmpeg -i bad_apple.webm -vf scale=80:60,rotate='PI/2:oh=iw:ow=ih+4' -f rawvideo -pix_fmt rgba -y out.bin
