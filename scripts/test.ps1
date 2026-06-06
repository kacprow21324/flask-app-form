$ErrorActionPreference = "Stop"

docker-compose build flask
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker-compose run --rm flask python -m unittest discover -s tests -v
exit $LASTEXITCODE
