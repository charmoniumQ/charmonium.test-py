import toolz  # type: ignore
import pathlib
import re
from typing import Iterable

import chardet

from ...util import expect_type, fs_escape, parse_one_bracketed_expression
from ...conditions import TrisovicCondition


def decode(source: bytes) -> str:
    encoding = expect_type(str, chardet.detect(source)["encoding"])
    return source.decode(encoding, errors="ignore")


def r_expr(string: str) -> str:
    quotes = {"\"", "'"}
    brackets = {
        "(": ")",
        "[": "]",
        "{": "}",
    }
    if not string:
        raise SyntaxError("Cannot find bracketed expression from empty string")
    if string[0] not in brackets.keys() | quotes:
        raise SyntaxError(f"String does not start with a bracket or quote: {string}")
    stack = [string[0]]
    for i, char in zip(range(1, len(string)), string[1:]):
        if stack[-1] == "\\":
            stack.pop()
            assert stack[-1] in quotes
        elif stack[-1] in quotes:
            if char == "\\":
                stack.append("\\")
            elif stack[-1] in quotes and char == stack[-1]:
                stack.pop()
        elif stack[-1] in brackets:
            if char in (brackets.keys() | quotes):
                stack.append(char)
            elif char in brackets.values():
                if char == brackets[stack[-1]]:
                    stack.pop()
                else:
                    raise SyntaxError(f"Bracket {stack[-1]} does not match {char}")
        else:
            raise RuntimeError(f"Unknown stack symbol: {stack[-1]}")
        if not stack:
            return string[0:i+1]
    raise SyntaxError(f"Unmatched left-brackets {stack} in {string}")


assert r_expr("(\"hello\", {[\"world\\\"\"]})") == "(\"hello\", {[\"world\\\"\"]})"
assert r_expr("\"hello\\\"' (world\"") == "\"hello\\\"' (world\""
try:
    r_expr("\"hello world\\\"")
except:
    pass
else:
    assert False
try:
    r_expr("(hello world")
except:
    pass
else:
    assert False


def replace_ranges(source: str, ranges: list[tuple[int, int, str]]) -> str:
    ret = []
    i = 0
    for start_replace, end_replace, replace_str in ranges:
        ret.append(source[i:start_replace])
        ret.append(replace_str)
        i = end_replace
    ret.append(source[i:])
    return "".join(ret)


setwd_pattern = re.compile(r"setwd \( (?P<delim>['\"])(?P<arg>.*?[^\\])(?P=delim)".replace(" ", r"\s*"))
assert expect_type(re.Match, setwd_pattern.match("setwd (\"hello \\\" () world\" )")).group("arg") == "hello \\\" () world"
def remove_setwd(source: str) -> tuple[str, list[str]]:
    setwd_arguments = []
    ranges = []
    for match in setwd_pattern.finditer(source):
        setwd_arguments.append(match.group("arg"))
        ranges.append((match.start("arg") - 1, match.end("arg") + 1, "'.'"))
    return replace_ranges(source, ranges), setwd_arguments


abs_path_pattern = re.compile(r"(?P<delim>['\"])(?P<abs_path>/.*?[^\\])(?P=delim)")
assert expect_type(re.Match, abs_path_pattern.match("'/hello/world'")).group("abs_path") == "/hello/world"
assert abs_path_pattern.match("'hello/world'") is None
def remove_abs_paths(source: str) -> tuple[str, list[tuple[str, str]]]:
    path_arguments = []
    ranges = []
    for match in abs_path_pattern.finditer(source):
        path_candidate = match.group("abs_path").replace("\\\"", "\"").replace("\\'", "'")
        path = pathlib.Path(path_candidate)
        if path_candidate.endswith("/"):
            replacement = "'./'"
        else:
            replacement = repr(str(path.name))
        path_arguments.append((match.group("abs_path"), replacement))
        ranges.append((match.start("abs_path"), match.end("abs_path"), replacement))
    return replace_ranges(source, ranges), path_arguments


install_packages_pattern = re.compile(r"install\.packages (?P<paren>\() ".replace(" ", r"\s*"))
assert install_packages_pattern.match("install.packages( c(\"abc\", \"def\"), something)") is not None
library_pattern = re.compile(r"(?P<function>library|require) \( (?P<delim>['\"])?(?P<package>[a-zA-Z0-9]+)(?P=delim)? [\),]".replace(" ", r"\s*"))
assert expect_type(re.Match, library_pattern.match("library(foo)")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("library('foo')")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("require(foo)")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("require('foo')")).group("package") == "foo"
colon_separator = re.compile(r"(?P<package>[a-zA-Z0-9]+)::(?P<identifier>\S*)")
assert expect_type(re.Match, colon_separator.match("foo::bar")).group("package") == "foo"
maximum_lookahead = 512
def separate_packages(source: str) -> tuple[str, list[str]]:
    packages = []
    for match in library_pattern.finditer(source):
        packages.append(match.group("package"))
    for match in colon_separator.finditer(source):
        packages.append(match.group("package"))
    install_packages_arguments = []
    ranges = []
    for match in install_packages_pattern.finditer(source):
        # Since an arbitrary R expression can be contained in install.packages("$package", ...)
        # and that expression may itself have nested parentheses,
        # it is not possible to match from vanilla regex.
        # Instead we pass it to a very simple char-by-char lexer.
        # The lexer knows about brackets (...) [...] {...} and strings "..." '...' and escapes within strings "...\"..."
        # The lexer will find the arugment to install.packages, so we can delete the call altogether.
        paren = match.start("paren")
        try:
            install_packages_argument = r_expr(source[paren : paren + maximum_lookahead])
        except SyntaxError as exc:
            raise RuntimeError("Could not parse:", source[match.start() : paren + maximum_lookahead]) from exc
        install_packages_arguments.append(install_packages_argument)
        assert source[paren : paren + len(install_packages_argument)] == install_packages_argument
        ranges.append((match.start(), paren + len(install_packages_argument), ""))
    return replace_ranges(source, ranges), packages


def main(
        r_file: pathlib.Path
) -> set[str]:
    source = decode(r_file.read_bytes())
    source, setwds_removed = remove_setwd(source)
    source, abs_to_rel_paths = remove_abs_paths(source)
    source, packages = separate_packages(source)
    r_file.write_text(source, encoding="UTF-8")
    return set(packages)


def generate_nix_flake(packages: Iterable[str], r_version: str) -> str:
    # Repeated from ./flake.nix
    # TODO: figure out how to not duplicate this
    nixpkgs = {
        # See https://lazamar.co.uk/nix-versions/?channel=nixpkgs-unstable&package=R
        # nix shell nixpkgs#nix-prefetch --command nix-prefetch fetchFromGitHub --owner NixOS --repo nixpkgs --rev 8ad5e8132c5dcf977e308e7bf5517cc6cc0bf7d8
        "4.2.2": ("8ad5e8132c5dcf977e308e7bf5517cc6cc0bf7d8", "sha256-0gI2FHID8XYD3504kLFRLH3C2GmMCzVMC50APV/kZp8="),
        "4.0.2": ("5c79b3dda06744a55869cae2cba6873fbbd64394", "sha256-mOTNMphTHk3xEn2v+U9AG94zn+zicQu6hpYdH8vdqY4="),
        "3.6.0": ("bea56ef8ba568d593cd8e8ffd4962c2358732bf4", "sha256-Ro3e5TxCnju0ssdRu9BgRyOiA3LsCQ3QYmWPefPOLwU="),
        "3.2.3": ("92487043aef07f620034af9caa566adecd4a252b", "sha256-DNmwVC3DQZNuBiN0rfyL3+TY9hQZx1p7IbhiBeTdzwE="),
        "3.2.2": ("42acb5dc55a754ef074cb13e2386886a2a99c483", "sha256-20ClstILkFwrSRTAu+7xZjtWyw38JvBNzvy3F/JW2fU="),
        "3.2.1": ("b860b106c548e0bcbf5475afe9e47e1d39b1c0e7", "sha256-3XyTRKdnqmm03053Ss53RpC69/j178f11pJXk5BFoWE="),
    }
    return (
        (pathlib.Path(__file__).parent / "flake_nix")
        .read_text()
        .replace("$nixpkgs_rev", nixpkgs[r_version][0])
        .replace("$nixpkgs_hash", nixpkgs[r_version][1])
        .replace("$packages", " ".join(f"\"{package}\"" for package in packages))
    )


# def init_tree_sitter() -> tree_sitter.Parser:
#     tree_sitter.Language.build_library(
#         "/nix/store/298b6jjfldxk4abaf9jn855bjhwlydkn-grammars",
#         [
#             './test-r',
#         ],
#     )
#     r_parser = tree_sitter.Parser()
#     r_parser.set_language(tree_sitter.Language('build/my-languages.so', 'r'))
#     return r_parser
