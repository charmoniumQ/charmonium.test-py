import toolz  # type: ignore
import pathlib
import re

import chardet

from ...util import expect_type, fs_escape, parse_one_bracketed_expression


def decode(source: bytes) -> str:
    encoding = expect_type(str, chardet.detect(source)["encoding"])
    return source.decode(encoding, errors="ignore")


def r_expr(string: str) -> str:
    brackets = {
        "(": ")",
        "[": "]",
        "{": "}",
        "\"": "\"",
        "'": "'",
    }
    if not string:
        raise SyntaxError("Cannot find bracketed expression from empty string")
    if string[0] not in brackets:
        raise SyntaxError(f"String does not start with a bracket: {string}")
    stack = [string[0]]
    for i, char in zip(range(1, len(string)), string[1:]):
        if stack[-1] == "\\":
            pass
        elif char == "\\" in stack[-1] in {"'", "\""}:
            stack.append("\\")
        elif char in brackets:
            stack.append(char)
        elif char == brackets[stack[-1]]:
            stack.pop()
        if not stack:
            return string[0:i+1]
    raise SyntaxError(f"Unmatched left-brackets {stack} in {string}")


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
        ranges.append((match.start("arg"), match.end("arg"), "'.'"))
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
        ranges.append((match.start("arg"), match.end("arg"), replacement))
    return replace_ranges(source, ranges), path_arguments


install_packages_pattern = re.compile(r"install\.packages (?P<paren>\() ".replace(" ", r"\s*"))
assert install_packages_pattern.match("install.packages( c(\"abc\", \"def\"), something)") is not None
library_pattern = re.compile(r"(?P<function>library|require) \( (?P<delim>['\"])?(?P<package>[a-zA-Z0-9]+)(?P=delim)? [\),]".replace(" ", r"\s*"))
assert expect_type(re.Match, library_pattern.match("library(foo)")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("library('foo')")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("require(foo)")).group("package") == "foo"
assert expect_type(re.Match, library_pattern.match("require('foo')")).group("package") == "foo"
maximum_lookahead = 512
def separate_packages(source: str) -> tuple[str, list[str]]:
    packages = []
    for match in library_pattern.finditer(source):
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
        install_packages_argument = r_expr(source[paren : paren + maximum_lookahead])
        install_packages_arguments.append(install_packages_argument)
        assert source[paren : paren + len(install_packages_argument)] == install_packages_argument
        ranges.append((match.start(), paren + len(install_packages_argument), ""))
    return replace_ranges(source, ranges), packages


def main(root: pathlib.Path, fix_paths: bool, fix_packages: bool, fix_order: bool) -> None:
    r_files = sorted([*root.glob("**/*.R"), *root.glob("**/*.r")])
    r_file_tuples: list[str] = []
    for r_file in r_files:
        source = decode(r_file.read_bytes())
        if fix_paths:
            source, setwds_removed = remove_setwd(source)
            source, abs_to_rel_paths = remove_abs_paths(source)
        if fix_packages:
            source, packages = separate_packages(source)
        r_file.write_text(source, encoding="UTF-8")
    if fix_order:
        raise NotImplementedError()


def get_r_script(
        r_files: list[pathlib.Path],
        code_dir: pathlib.Path,
        out_dir: pathlib.Path,
) -> str:
    r_file_tuples: list[str] = []
    for r_file in r_files:
        r_file = r_file.relative_to(code_dir)
        r_file_result = out_dir / fs_escape(str(r_file))
        r_file_tuples.append("list({r_file!s}, {r_file_result!s})")
    return f"failed <- list({', '.join(r_file_tuples)})\n" + """
    library(subprocess)
    new_successes = TRUE
    write("", file="order.txt")
    function()
    while (new_successes) {
        new_failures = list()
        new_successes = FALSE
        for (i in 1:length(failed)) {
            handle <- spawn_process("timeout", "-k", "30", "1800", "Rscript", failed[[i]][[1]])
            status <- process_wait(handle)
            if (status == 0) {
                new_successes = TRUE
                write(paste(failed[[i]][[1]], "\n"), file="order.txt", append=TRUE)
            } else {
                list.append(new_failures, failed[[i]])
            }
            stdout <- process_read(handle, pipe=PIPE_STDOUT, timeout=TIMEOUT_IMMEDIATE, flush=TRUE)
            stderr <- process_read(handle, pipe=PIPE_STDERR, timeout=TIMEOUT_IMMEDIATE, flush=TRUE)
            write(stdout, paste(failed[[i]][[2]], "/stdout", sep=""))
            write(stderr, paste(failed[[i]][[2]], "/stderr", sep=""))
            write(paste(status), paste(failed[[i]][[2]], "/status", sep=""))
        }
        failed <- new_failures
    }
    """


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
