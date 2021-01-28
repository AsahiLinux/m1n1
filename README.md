# m1n1: an experimentation playground for Apple Silicon

(And perhaps some day a Linux bootloader)

* Needs submodule artwork installed so populate submodule if not recursively cloned:
<pre>
    git submodule init
    git submodule update
</pre>
* Build with (requires gcc-aarch64-linux-gnu on debian/buster)
<pre>
    make
</pre>
## License

m1n1 is licensed under the MIT license, as included in the [LICENSE](LICENSE) file.

* Copyright (C) 2021 The Asahi Linux contributors

Please see the Git history for authorship information.

Portions of m1n1 are based on mini:

* Copyright (C) 2008-2010 Hector Martin "marcan" <marcan@marcan.st>
* Copyright (C) 2008-2010 Sven Peter <sven@svenpeter.dev>
* Copyright (C) 2008-2010 Andre Heider <a.heider@gmail.com>

m1n1 embeds libfdt, which is dual [BSD](3rdparty_licenses/LICENSE.BSD-2.libfdt) and
[GPL-2](3rdparty_licenses/LICENSE.GPL-2) licensed and copyright:

* Copyright (C) 2006 David Gibson, IBM Corporation.

The ADT code in mini is also based on libfdt and subject to the same license.

m1n1 embeds [minlzma](https://github.com/ionescu007/minlzma), which is
[MIT](3rdparty_licenses/LICENSE.minlzma) licensed and copyright:

* Copyright (c) 2020 Alex Ionescu

m1n1 embeds a slightly modified version of [tinf](https://github.com/jibsen/tinf), which is
[ZLIB](3rdparty_licenses/LICENSE.tinf) licensed and copyright:

* Copyright (c) 2003-2019 Joergen Ibsen
