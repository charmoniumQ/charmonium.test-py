This directory was sourced from [Trisovic et al.][1] with modifications to make it run.

See `diff` for a list of modifications.

[1]: https://github.com/atrisovic/dataverse-r-study/tree/master/docker

# Analysis environment

Building the Docker image:

```
docker build -t aws-image .
```

## Testing with existing image

Test workflow on a local computer:

```
docker pull atrisovic/aws-image
docker run -d --name=logtest -e DOI='doi:10.7910/DVN/VCFMBI' -e TEST='True' aws-image
# see what's happening in the container
docker attach logtest
docker rm logtest
```

On AWS executed as:

```
docker run -e DOI='doi:10.7910/DVN/VCFMBI' atrisovic/aws-image
```
