out_dir <- out_dir_from_python
code_dir <- code_dir_from_python
r_file_tuples <- list(r_file_tuples_from_python)
timeout <- timeout_from_python
use_nix <- use_nix_from_python

setwd(code_dir)
new_successes = TRUE
write("", file=paste(out_dir, "/", order))
failed <- r_file_tuple
nix_command = if (use_nix) " nix develop --command " else " "
while (new_successes) {
    new_failures = list()
    new_successes = FALSE
    for (i in 1:length(failed)) {
        system(paste(
            "timeout -k ",
            timeout,
            nix_command,
            "Rscript",
            shQuote(failed[[i]][[1]]),
            " >",
            failed[[i]][[2]],
            "/stdout 2>",
            failed[[i]][[2]],
            "/stderr",
            sep="",
        ), wait=TRUE,)
        if (status == 0) {
            new_successes = TRUE
            write(paste(failed[[i]][[1]], "\n"), file=paste(out_dir, "/", order), append=TRUE)
        } else {
            list.append(new_failures, failed[[i]])
        }
        write(stdout, paste(failed[[i]][[2]], "/stdout", sep=""))
        write(stderr, paste(failed[[i]][[2]], "/stderr", sep=""))
        write(paste(status), paste(failed[[i]][[2]], "/status", sep=""))
    }
    failed <- new_failures
}
