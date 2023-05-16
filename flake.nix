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
        # https://discourse.nixos.org/t/using-non-free-libraries-in-flakes/8632/18
        pkgs = import nixpkgs {
          inherit system;
        };
        p2n = poetry2nix.legacyPackages.${system};
        pyproject = builtins.fromTOML(builtins.readFile(./pyproject.toml));
        name = builtins.replaceStrings ["." "_"] ["-" "-"] pyproject.tool.poetry.name;
        default-python = pkgs.python311;
        nix-dev-dependencies = [
          pkgs.poetry
          pkgs.terraform
          pkgs.azure-cli
          pkgs.jq
          pkgs.sqlite
          #pkgs.diffoscope
        ];
        nix-site-dependencies = [
          pkgs.hwloc
          pkgs.gitMinimal
          pkgs.file
        ];
        # see https://lazamar.co.uk/nix-versions/
        getOldNixpkgs = nixpkgsGitHash:
          import (builtins.fetchGit {
            name = "old-nixpkgs";
            url = "https://github.com/NixOS/nixpkgs/";
            ref = "refs/heads/nixpkgs-unstable";
            rev = nixpkgsGitHash;
          }) {
            inherit system;
          };
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
          attrs = [ "hatchling" "hatch-fancy-pypi-readme" "hatch-vcs" ];
          dask = [ "versioneer" ];
          distributed = [ "versioneer" ];
          types-aiofiles = [ "setuptools" ];
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

        # TODO: move this to dockerfiles/flake.nix
        r-versions = {
          # See https://lazamar.co.uk/nix-versions/?channel=nixpkgs-unstable&package=R
          "4.2.2" = "8ad5e8132c5dcf977e308e7bf5517cc6cc0bf7d8";
          "4.0.2" = "5c79b3dda06744a55869cae2cba6873fbbd64394";
          "3.6.0" = "bea56ef8ba568d593cd8e8ffd4962c2358732bf4";
          "3.2.4" = "c0c50dfcb70d48e5b79c4ae9f1aa9d339af860b4";
          "3.2.3" = "92487043aef07f620034af9caa566adecd4a252b";
          "3.2.2" = "42acb5dc55a754ef074cb13e2386886a2a99c483";
          "3.2.1" = "b860b106c548e0bcbf5475afe9e47e1d39b1c0e7";
        };

        # Read the source of buildLayeredImage for info on how to do stuff:
        # https://github.com/NixOS/nixpkgs/blob/master/pkgs/build-support/docker/default.nix
        r-runner-contents = r-version:
          let
            nixpkgsRev = (builtins.getAttr r-version r-versions);
            oldNixpkgs = (getOldNixpkgs nixpkgsRev);
          in [
            # Required by for this image to work with measure_docker_command:
            oldNixpkgs.time
            oldNixpkgs.bash

            # To do grayson_code_cleaning with packages:
            oldNixpkgs.nix

            # Needed for build infrastructure:
            # The parnetheses show the Debian package popularity rank
            oldNixpkgs.stdenv
            # TODO: figure out how to not write these directly:
            # Just include everything in oldNixpkgs.stdenv

            oldNixpkgs.which
            oldNixpkgs.coreutils # (6)
            oldNixpkgs.gnutar # (9)
            oldNixpkgs.gnused # (18)
            oldNixpkgs.findutils # (23)
            oldNixpkgs.gnugrep # (29)
            oldNixpkgs.gzip # (30)
            oldNixpkgs.gawk # (mawk is 59; Nix defaults awk to gawk)
            oldNixpkgs.diffutils # (70)
            oldNixpkgs.file # (118)
            oldNixpkgs.xz # (124)
            oldNixpkgs.bzip2 # (136)
            oldNixpkgs.gnumake # (488)
            # oldNixpkgs.gcc
            oldNixpkgs.patch # (329)
            oldNixpkgs.cacert # Needed for any/all HTTPS. Debian doesn't need this, but we do.
            oldNixpkgs.gitMinimal # (589)
            # Note that oldNixpkgs for 3.2.3 does not have pkg-config :(
            oldNixpkgs.pkg-config # (1801) install.packages needs this to find other dependencies

            # Libs:
            oldNixpkgs.curl
            oldNixpkgs.curl.dev # (169) R curl links against libcurl
            oldNixpkgs.zlib
            oldNixpkgs.zlib.dev # (2132) R httpuv links against libz
            oldNixpkgs.cmake # (2789)
            oldNixpkgs.openssl
            oldNixpkgs.openssl.dev # (2562) R openssl links against libopenssl
            oldNixpkgs.libxml2
            oldNixpkgs.libxml2.dev # (3682) R xml2 links against libxml2
            oldNixpkgs.libpng
            oldNixpkgs.libpng.dev # (3109)
            oldNixpkgs.libjpeg
            oldNixpkgs.libjpeg.dev # 4176
            oldNixpkgs.udunits # (8375)
            oldNixpkgs.nlopt # (9360)
            (oldNixpkgs.rWrapper.override {
              packages = with oldNixpkgs.rPackages; [
                # R-recommended according to: https://anaconda.org/r/r-recommended/files
                KernSmooth
                MASS
                Matrix
                boot
                class
                cluster
                codetools
                foreign
                lattice
                mgcv
                nlme
                nnet
                rpart
                spatial
                survival
              ];
            })
          ];
        r-runner-image = r-version:
          let
            nixpkgsRev = (builtins.getAttr r-version r-versions);
            oldNixpkgs = (getOldNixpkgs nixpkgsRev);
            real-contents = (r-runner-contents r-version);
          in pkgs.dockerTools.buildLayeredImage {
            name = "r-runner-${builtins.replaceStrings ["."] ["-"] r-version}";
            contents = real-contents ++ [
              (pkgs.runCommandLocal "setup" { } ''
                mkdir $out

                # R depends on /tmp
                mkdir $out/tmp

                # R depends on /usr/bin/env
                mkdir -p $out/usr/bin/
                ln -s ${oldNixpkgs.coreutils}/bin/env $out/usr/bin/env

                # Make users (root, nobody, nixbld)
                mkdir $out/etc
                echo -e 'root:x:0:0:root user:/home/root:/bin/sh\nnixbld1:x:1:1:Build user:/var/empty:/noshell\nnobody:x:65534:65534:nobody:/var/empty:/bin/sh\n' > $out/etc/passwd
                echo -e 'root:x:0:\nnixbld:x:1:nixbld1\nnobody:x:65534:\n' > $out/etc/group
                mkdir -p $out/home/root/ $out/var/empty

                # Set up ~/.Rprofile
                echo -e 'local({r <- getOption("repos");\n  r["CRAN"] <- "http://cran.us.r-project.org";\n  options(repos=r);\n});\n.libPaths("~/.R/lib");\noptions(warn=1);\n' > $out/home/root/.Rprofile
                mkdir -p $out/home/root/.R/lib
                echo -e "CFLAGS=-I/include\nLDFLAGS=-L/lib\n" >> $out/home/root/.R/Makevars

                # Enable Nix command and Nix flakes
                mkdir -p $out/home/root/.config/nix
                echo "experimental-features = nix-command flakes" >> $out/home/root/.config/nix/nix.conf
                # We copy a bunch of /nix/store/... paths to the image.
                # BUT if a /nix/store/... path is not in the Nix DB, Nix doesn't know about it.
                # Therefore, we will also copy our Nix DB into the image.
                # If there are paths in the Nix DB that is not in the /nix/store/..., Nix just rebuilds them (no harm, no foul)
                mkdir -p $out/nix/var/nix/db
                export USER=root

                echo '${nixpkgsRev}' > $out/nixpkgs_rev

                # Write ~/.profile
                echo 'source ${oldNixpkgs.cacert}/nix-support/setup-hook' >> $out/home/root/.profile
                echo 'export PKG_CONFIG_PATH=/lib/pkgconfig' >> $out/home/root/.profile
                echo 'export USER=root' >> $out/home/root/.profile
              '')
            ];
            extraCommands = ''
              export NIX_REMOTE=local?root=$PWD
              ${pkgs.buildPackages.nix}/bin/nix-store --verify --check-contents --repair < ${pkgs.closureInfo {rootPaths = real-contents;}}/registration
            '';
            maxLayers = 125;
            
            config = {
              Entrypoint = [
                "/bin/sh" "--login" "-c"
              ];
            };
            # Tests for this contianer
            # cd ; pwd # /home/root
            # nix shell nixpkgs#hello --command hello
            # pkg-config zlib --libs # should have -L/nix/store/...
            # Rscript -e 'download.file("https://example.com", "test")'
            # Rscript -e 'install.packages(c("xml2", "cregg", "dpylr"))' # should go to ~/.R/libs
            # which cmake awk
            # Mount /path/to/flake/with/dollar/vars/substituted as /host.
            # env --chdir /host nix develop --command R --version
            # This should take <1min
            # Downloading nixpkgs is necessary, but that should be relatively fast (over HTTPS not git)
            # It should not be downloading paths that already exist in the store.
          };
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
            maxLayers = 125;
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
        } // (builtins.listToAttrs
          (builtins.map
            (r-version: {
              name = "r-runner-${builtins.replaceStrings ["."] ["-"] r-version}";
              value = r-runner-image r-version;
            }
            )
            (builtins.attrNames r-versions))
        );

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
