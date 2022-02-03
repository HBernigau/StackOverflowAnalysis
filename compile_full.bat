pip-compile --output-file=requirements\full.txt requirements.in\full.txt
pip-compile --output-file=requirements\essentials.txt requirements.in\essentials.txt
COPY ".\requirements\essentials.txt" ".\Docker\py\essentials.txt"