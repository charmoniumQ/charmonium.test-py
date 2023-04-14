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
        # see https://lazamar.co.uk/nix-versions/
        oldNixpkgs = nixpkgsGitHash:
          import (builtins.fetchGit {
            name = "old-nixpkgs";
            url = "https://github.com/NixOS/nixpkgs/";
            ref = "refs/heads/nixpkgs-unstable";
            rev = nixpkgsGitHash;
          }) {};
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
          beautifulsoup4 = [ "hatchling" ];
          xyzservices = [ "setuptools" ];
          simpervisor = [ "setuptools" ];
          pandas = [ "versioneer" ];
          jupyter-server-proxy = [ "setuptools" "jupyter-packaging" ];
          dask-labextension = [ "jupyter-packaging" ];
          urllib3-secure-extra = [ "flit-core" ];
          azure-mgmt-appcontainers = [ "setuptools" ];
          azure-cli-core = [ "setuptools" ];
          azure-cli = [ "setuptools" ];
        };
        p2n-overrides' = p2n.defaultPoetryOverrides.extend (self: super:
          builtins.mapAttrs (package: build-requirements:
            (builtins.getAttr package super).overridePythonAttrs (old: {
              buildInputs = (old.buildInputs or [ ]) ++ (builtins.map (pkg: if builtins.isString pkg then builtins.getAttr pkg super else pkg) build-requirements);
            })
          ) pypkgs-build-requirements
        );
        p2n-overrides = p2n-overrides'.extend (self: super:
          let
            # https://github.com/Azure/azure-cli/issues/14416
            # https://github.com/NixOS/nixpkgs/blob/nixos-22.11/pkgs/tools/admin/azure-cli/python-packages.nix
            # Also note, azure is a "namespace package", no __init__ required.
            # If it is present, it will "conflict" with other azure packages that want to create their own __init__.py
            fix-old-azure-packages = ''
              echo "--- Patching setup.py ---"
              sed --in-place 's/except ImportError:/except ImportError as exc:\n    raise exc/g' setup.py
              head --lines 20 setup.py
              echo "------------------------"

              echo "--- Patching azure_bdist_wheel.py --"
              sed --in-place \
                  -e 's/from wheel.pep425tags.*/from wheel.bdist_wheel import get_abi_tag, get_platform/g' \
                  -e 's/from wheel.util.*//g' \
                  -e 's/from wheel.archive.*//g' \
                  -e 's/get_abbr_impl()/"cp"/g' \
                  -e 's/get_impl_ver()/"311"/g' \
                  -e 's/native(\(.*\))/(\1).decode()/g' \
                  -e 's/open_for_csv(\(.*\))/open(\1, {"newline": ""})/g' \
                  azure_bdist_wheel.py
              head --lines 70 azure_bdist_wheel.py | tail --lines 15
              echo "------------------------"
            '';
          in
          {
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
          # azure-mgmt-consumption = super.azure-mgmt-consumption.overridePythonAttrs (
          #   old:
          #   {
          #     preBuild = (old.preBuild or "") + fix-old-azure-packages;
          #   }
          # );
          # azure-mgmt-datalake-analytics = super.azure-mgmt-datalake-analytics.overridePythonAttrs (
          #   old:
          #   {
          #     preBuild = (old.preBuild or "") + fix-old-azure-packages;
          #   }
          # );
          # azure-mgmt-relay = super.azure-mgmt-relay.overridePythonAttrs (
          #   old:
          #   {
          #     preBuild = (old.preBuild or "") + fix-old-azure-packages;
          #   }
          # );
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

          "jupyter-image" = pkgs.dockerTools.buildLayeredImage {
            name = "jupyter-image";
            contents = [
              (p2n.mkPoetryEnv {
                projectDir = ./dockerfiles/jupyter;
                python = default-python;
                overrides = p2n-overrides;
              })
            ];
          };

          "r-runner" = pkgs.dockerTools.buildLayeredImage {
            name = "r-runner";
            tag = "3.2.4";
            contents = [
              ((oldNixpkgs ((import ./dockerfiles/r-versions.nix)."3.0.3")).R)
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
            shellHook = ''
              export AZURE_CLI_PYTHONPATH=$PYTHONPATH
              export PYTHONPATH=
              # azure-cli adds all of its azure-* packages to the PYTHONPATH
              # which conflict with the packages in the Poetry env.
              # The `az` wrapper script sets its own PYTHONPATH, so we don't need that
            '';
          };
        };

        # defaultPackage = self.packages.${system}.${name};
      });
}
