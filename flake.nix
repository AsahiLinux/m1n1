{
  description = "an experimentation playground for Apple Silicon";

  inputs.flake-compat = {
      url = "github:edolstra/flake-compat";
      flake = false;
    };

  outputs = { self, nixpkgs, ... }: let
    version = self.shortRev or (toString self.lastModifiedDate);

    systems = [ "aarch64-darwin" "aarch64-linux" ];

    forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f system);

    # Memoize nixpkgs for different platforms for efficiency.
    nixpkgsFor = forAllSystems (system:
      import nixpkgs {
        inherit system;
        overlays = [ self.overlay ];
      });

    cleanSrc = (src: with nixpkgs.lib; cleanSourceWith {
        filter = name: type: cleanSourceFilter name type
          && !(hasInfix "/node_modules/" name)
          && !(hasInfix "/nix/" name && hasSuffix ".nix" name)
        ;
        inherit src;
      }) ./.;
  in {
    overlay = final: prev: {
      m1n1 = final.callPackage (
        { lib, imagemagick, llvmPackages_13, dtc }:
        llvmPackages_13.stdenv.mkDerivation {
          pname = "m1n1";
          inherit version;

          src = cleanSrc;

          outputs = [ "out" ];

          TOOLCHAIN = "";
          USE_CLANG = 1;

          nativeBuildInputs = [ imagemagick llvmPackages_13.llvm llvmPackages_13.bintools dtc ];

          installPhase = ''
          mkdir -p "$out/"
          cp build/m1n1.macho "$out/"
          cp build/m1n1-raw.elf "$out/"
          cp build/m1n1.bin "$out/"
          '';
        }
      ) {};
    };

    packages =
      forAllSystems (system: { inherit (nixpkgsFor.${system}) m1n1; });

    defaultPackage = forAllSystems (system: self.packages.${system}.m1n1);

  };
}
