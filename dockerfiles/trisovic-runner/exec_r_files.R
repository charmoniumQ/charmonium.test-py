local_args = commandArgs(trailingOnly=TRUE)
# parse command line args for path to the directory and preprocessing
dir_path_doi = local_args[1]

setwd("/usr/workdir")
library(stringr, quietly=TRUE, warn.conflicts=FALSE)

# Install if not already isntalled.
# Sometimes, we install this with Conda in the Dockerfile
# We might run the script twice in an interactive session, so only install once.
if (!require(R.utils, quietly=TRUE, warn.conflicts=FALSE)) {
	install.packages("R.utils", quiet=TRUE)
	library(R.utils, quietly=TRUE, warn.conflicts=FALSE)
}

if (!require(reticulate, quietly=TRUE, warn.conflicts=FALSE)) {
	install.packages("reticulate", quiet=TRUE)
	library(reticulate, quietly=TRUE, warn.conflicts=FALSE)
}

r_files = list.files(".", pattern="\\.[Rr]\\>", recursive=FALSE, full.names=FALSE)
r_files <- r_files[r_files != "exec_r_files.R"]
print(r_files)

for (r_file in r_files) {
	print(paste("Executing: ", r_file))

	# parse out file name, leaving out the ".R" part
	filename = substr(r_file, 1, nchar(r_file) - 2)

	save(dir_path_doi, r_files, r_file, filename,
		 file="get_reprod.RData")


	# try to run the R file with error handling
	error <- withTimeout({ 
		try(source(r_file), silent = TRUE);
	}, timeout=3600, onTimeout="silent");

	local_vars <- c('dir_path_doi', 'arg_temp', 'local_args', 'local_vars', 'external_vars', 'get_readability_metrics', 'error', 'filename', 'r_file', 'r_files', 'new_log_data', 'noauth', 'planb')
	external_vars <- ls()
	external_vars <- external_vars[!external_vars %in% local_vars]

	# restore local variables
	load("get_reprod.RData")

	use_python("/opt/conda/envs/py3/bin/python3.5")
	source_python('readability_analysis.py')
	arg_temp <- paste(external_vars, collapse=' ')
	get_readability_metrics(arg_temp, filename=r_file) 

	# if there was an error

	if (class(error) == "try-error") {
            # trim whitespace from beginning and end of string
	    error = str_trim(error[1])
	    # parse all the quotes from the error string
	    error = str_replace_all(error, "\"", "'")
		# parse all the quotes from the error string
	    error = str_replace_all(error, "‘", "'") 
		error = str_replace_all(error, "’", "'")
	    # replace all newline characters in middle of string with special string
	    error = str_replace_all(error, "[\n]", "")
	}
	else {
		error = "success"
		}
	
	# Plan B - source cannot parse R file and sees 
	# syntax errors even when there are none
	planb <- c("Error in source", "unexpected")
	if (all(sapply(planb, grepl, error))){
		print("Running plan B")
		
		# try rerunning script with python
		use_python("/opt/conda/envs/py3/bin/python3.5")

		source_python('execute_files.py')
		error = execute_files(r_file)
	}  
	
	if (grepl("reached CPU time limit", error, fixed = TRUE)){
		error = "time limit exceeded"
	}

	noauth <- c("status", "ERROR")
	if (all(sapply(noauth, grepl, error))){
		error = "not authorized"
	}          

	# create dataframe from doi, filename, and errors to facilitate csv writing
	new_log_data = data.frame(doi=c(dir_path_doi), filename=c(r_file),
							  error=c(error), stringsAsFactors = FALSE)
	# write the new log data into the log file
	write.table(new_log_data, file="run_log.csv", sep=",", append=TRUE,
				row.names=FALSE, col.names=FALSE)

	}
