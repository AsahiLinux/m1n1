#!/bin/bash

yt-dlp 'https://www.youtube.com/watch?v=UkgK8eUdpAo'
ffmpeg -i *.webm -vf scale=80:60 crushed.mkv
ffmpeg -i crushed.mkv -f rawvideo -pix_fmt rgb24 out.bin
