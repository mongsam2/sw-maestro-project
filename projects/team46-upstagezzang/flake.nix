{
  description = "SW Maestro project planning assistant";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-build-systems.url = "github:pyproject-nix/build-system-pkgs";
  };

  outputs =
    {
      nixpkgs,
      flake-utils,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        lib = pkgs.lib;

        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

        python = pkgs.python313;

        pythonBase = pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        };

        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        pythonSet = pythonBase.overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            overlay
          ]
        );

        editableOverlay = workspace.mkEditablePyprojectOverlay {
          root = "$REPO_ROOT";
        };

        editablePythonSet = pythonSet.overrideScope editableOverlay;

        virtualenv = editablePythonSet.mkVirtualEnv "asmchat-dev-env" workspace.deps.all;
      in
      {
        packages.default = pythonSet.mkVirtualEnv "asmchat-env" workspace.deps.default;

        devShells.default = pkgs.mkShell {
          packages = [
            virtualenv
            pkgs.uv
            pkgs.podman-compose
            pkgs.podman
            pkgs.just
            pkgs.ruff
          ];

          env = {
            UV_NO_SYNC = "1";
            UV_PYTHON = editablePythonSet.python.interpreter;
            UV_PYTHON_DOWNLOADS = "never";
          };

          shellHook = ''
            unset PYTHONPATH
            export REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
            export PYTHONPATH="$REPO_ROOT/src:$PYTHONPATH"
            echo "dev environment ready"
          '';
        };
      }
    );
}
