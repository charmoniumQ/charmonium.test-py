{
  inputs = {
    flake-utils = {
      url = "github:numtide/flake-utils";
    };
    nix-utils = {
      url = "github:charmoniumQ/nix-utils";
    };
    nix-documents = {
      url = "github:charmoniumQ/nix-documents";
    };
  };
  outputs = { self, nixpkgs, flake-utils, nix-utils, nix-documents }:
    {
      templates = {
        default = {
          path = ./templates;
          description = "Template for making documents as a Nix Flake";
        };
      };
    } // flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          nix-lib = nixpkgs.lib;
          nix-utils-lib = nix-utils.lib.${system};
          nix-documents-lib = nix-documents.lib.${system};
        in
        {
          packages = {
            default = nix-utils-lib.mergeDerivations {
              packageSet = nix-utils-lib.packageSetRec
                (self: [
                  (nix-documents-lib.markdownDocument {
                    src = nix-utils-lib.mergeDerivations {
                      packageSet = {
                        "." = ./trisovic-replication;
                        "template.latex"= ./template.latex;
                      } // nix-utils-lib.packageSet [ self."class_diagram.svg" ];
                    };
                    main = "main.md";
                    name = "trisovic-replication.pdf";
                    outputFormat = "pdf";
                    date = 1683922109; # date +%s
                  })
                  (nix-documents-lib.plantumlFigure {
                    src = ./trisovic-replication;
                    main = "class_diagram.plantuml";
                    name = "class_diagram.svg";
                  })
                ]);
            };
          };
        });
}
