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
    };
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pyproject = builtins.fromTOML(builtins.readFile(./pyproject.toml));
        name = builtins.replaceStrings ["." "_"] ["-" "-"] pyproject.tool.poetry.name;
        default-python = pkgs.python311;
        nix-dev-dependencies = [
          pkgs.poetry
          pkgs.hwloc
        ];
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

          "${name}-app" = pkgs.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            # default Python for shell
            python = default-python;
            groups = ["dev"];
            overrides = pkgs.poetry2nix.overrides.withDefaults (self: super: {
              charmonium-test-py = super.charmonium-freeze.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.poetry];
              });
              charmonium-time-block = super.charmonium-freeze.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.poetry];
              });
              charmonium-cache = super.charmonium-freeze.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.poetry];
              });
              charmonium-freeze = super.charmonium-freeze.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.poetry];
              });
              azure-cli-telemetry = super.azure-cli-telemetry.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.setuptools];
              });
              types-tqdm = super.types-tqdm.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.setuptools];
              });
              pyproject-api = super.pyproject-api.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.hatchling self.hatch-vcs];
              });
              tox = super.tox.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.hatchling];
              });
              universal-pathlib = super.universal-pathlib.overrideAttrs (old: {
                nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.flit-core];
              });
              # pygithub = super.pygithub.overrideAttrs (old: {
              #   nativeBuildInputs = (old.nativeBuildInputs or []) ++ [self.setuptools-scm-3132412841];
              # });
            });
          };
  
          "${name}-pure-shell" = pkgs.mkShell {
            buildInputs = nix-dev-dependencies ++ [
              (pkgs.poetry2nix.mkPoetryEnv {
                projectDir = ./.;
                # default Python for shell
                python = default-python;
              })
            ];
            # TODO: write a check expression (`nix flake check`)
          };
  
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
        };

        devShell = self.packages.${system}."${name}-shell";

        # defaultPackage = self.packages.${system}.${name};
      });
}
