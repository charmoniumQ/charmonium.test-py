{
  inputs = {
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
    nixpkgs = {
      url = "github:NixOS/nixpkgs";
    };
    poetry2nix = {
      url = "github:nix-community/poetry2nix";
      inputs = {
        nixpkgs = {
          follows = "nixpkgs";
        };
      };
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        p2n = poetry2nix.legacyPackages.${system};
        pyproject = builtins.fromTOML(builtins.readFile(./pyproject.toml));
        name = builtins.replaceStrings ["." "_"] ["-" "-"] pyproject.tool.poetry.name;
        default-python = pkgs.python311;
        nix-dev-dependencies = [
          pkgs.poetry
          pkgs.terraform
          pkgs.azure-cli
          pkgs.jq
        ];
        nix-site-dependencies = [
          pkgs.hwloc
        ];
        # See https://github.com/nix-community/poetry2nix/blob/master/overrides/build-systems.json
        # and https://github.com/nix-community/poetry2nix/blob/master/docs/edgecases.md
        pypkgs-build-requirements = {
          charmonium-test-py = [ "poetry" ];
          charmonium-time-block = [ "poetry" ];
          charmonium-freeze = [ "poetry" ];
          charmonium-cache = [ "poetry" ];
          azure-cli-telemetry = [ "setuptools" ];
          types-tqdm = [ "setuptools" ];
          pyproject-api = [ "hatchling" "hatch-vcs"];
          tox = [ "hatchling" "hatch-vcs" ];
          universal-pathlib = [ "flit-core" ];
          pygithub = [ "setuptools-scm" ];
        };
        p2n-overrides' = p2n.defaultPoetryOverrides.extend (self: super:
          builtins.mapAttrs (package: build-requirements:
            (builtins.getAttr package super).overridePythonAttrs (old: {
              buildInputs = (old.buildInputs or [ ]) ++ (builtins.map (pkg: if builtins.isString pkg then builtins.getAttr pkg super else pkg) build-requirements);
            })
          ) pypkgs-build-requirements
        );
        p2n-overrides = p2n-overrides'.extend (self: super: {
          pillow = super.pillow.overridePythonAttrs (
            old:
            let
              oldPreConfigure = old.preConfigure or "";
              oldPreConfigure' = if builtins.isList oldPreConfigure then builtins.concatStringsSep "\n" oldPreConfigure else oldPreConfigure;
              addLibrary = lib: ''
                export C_INCLUDE_PATH="${if builtins.hasAttr "dev" lib then lib.dev else lib.out}/include:$C_INCLUDE_PATH"
                export LIBRARY_PATH="${lib.out}/lib:$LIBRARY_PATH"
              '';
              librariesToAdd = [ pkgs.freetype pkgs.libjpeg pkgs.openjpeg pkgs.libimagequant pkgs.zlib pkgs.lcms2 pkgs.libtiff pkgs.tcl ];
            in
              {
                nativeBuildInputs = (old.nativeBuildInputs or [ ])
                                    ++ [ pkgs.pkg-config self.pytest-runner ];
                buildInputs = with pkgs; (old.buildInputs or [ ])
                                         ++ [ pkgs.libxcrypt pkgs.libwebp ]
                                         ++ librariesToAdd
                                         ++ pkgs.lib.optionals (lib.versionAtLeast old.version "7.1.0") [ pkgs.xorg.libxcb ]
                                         ++ pkgs.lib.optionals (self.isPyPy) [ pkgs.tk pkgs.xorg.libX11 ];
                preConfigure = oldPreConfigure'
                               + builtins.concatStringsSep "\n" (map addLibrary librariesToAdd)
                               + "\nsed 's|DEBUG = False|DEBUG = True|g' -i setup.py\n";
              }
          );
        });
      in {
        packages = {
          # There are two approaches to make a poetry project work in Nix:
          # 1. Use Nix to install dependencies in poetry.lock.
          # 2. Use Nix to install Poetry and use Poetry to install dependencies in poetry.lock.
          # Option 2 is less elegant, because it uses a package manager to install a package manager.
          # For example, to effectively cache the environment in CI, I have to cache the Nix store and the Poetry venv.
          # But at the time of writing poetry2nix DOES NOT WORK with Python's cryptography.
          # Cryptography is a core dependency, so it won't work at all.
          # ${name-pure-shell} is option 1, ${name-shell} is option 2.

          "${name}-shell" = pkgs.mkShell {
            buildInputs = nix-dev-dependencies ++ [default-python];
            shellHook = ''
              if [ ! -f poetry.lock ] || [ ! -f build/poetry-$(sha1sum poetry.lock | cut -f1 -d' ') ]; then
                  poetry install --sync
                  if [ ! -d build ]; then
                      mkdir build
                  fi
                  touch build/poetry-$(sha1sum poetry.lock | cut -f1 -d' ')
              fi
              export PREPEND_TO_PS1="(${name}) "
              export PYTHONNOUSERSITE=true
              export VIRTUAL_ENV=$(poetry env info --path)
              export PATH=$VIRTUAL_ENV/bin:$PATH
              #export LD_LIBRARY_PATH=${pkgs.gcc-unwrapped.lib}/lib:$LD_LIBRARY_PATH
            '';
            # TODO: write a check expression (`nix flake check`)
          };
          "${name}-image" = pkgs.dockerTools.buildLayeredImage {
            name = "${name}";
            contents = [
              # pkgs.dash
              pkgs.busybox
              (p2n.mkPoetryEnv {
                projectDir = ./.;
                python = default-python;
                groups = [ "site" ];
                overrides = p2n-overrides;
              })
            ] ++ nix-site-dependencies;
          };

          "jupyterlab-image" = pkgs.dockerTools.buildLayeredImage {
            name = "jupyterlab-image";
            contents = [
              (p2n.mkPoetryEnv {
                projectDir = ./dockerfiles/jupyterlab_container;
                python = default-python;
                overrides = p2n-overrides;
              })
            ];
          };
        };

        devShells = rec {
          impure-shell = self.packages.${system}."${name}-shell";
          default = pure-shell;
          pure-shell = pkgs.mkShell {
            packages = [
              (p2n.mkPoetryEnv {
                projectDir = ./.;
                python = default-python;
                groups = [ "site" "dev" ];
                overrides = p2n-overrides;
              })
            ] ++ nix-dev-dependencies ++ nix-site-dependencies;
          };
        };

        # defaultPackage = self.packages.${system}.${name};
      });
}
