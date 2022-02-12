# StackOverflowAnalysis

The current application provides an **analysis framework for stack overflow posts**.

The following features are supported:

- automatic loading of stack-overflow posts with some specific tag (for example "microservices")
- automatic parsing of stack-overflow posts and extraction of content and various meta data fields
- automatic persistence of content and meta data in appropriate back-end data bases for further analysis
- automatic execution of topic learning via latent Dirichlet allocation (LDA)
- automatic generation of analysis artefacts for topics (word cloud and LDAvis)
- Jupyter notebook for presentation of several descriptive statistics of the corpus
  and LDA results
- Jupyter notebook for analysis of the contributor networks for these posts

On the technical side the application uses:

- Docker
- PostgreSQL
- Elastic search
- Prefect
- Dask
- and: lots of Python

## How to proceed

| :warning: Currently the code cannot be executed. |
|:--- |
| The reason is a structural change in the html code served by stack-overflow servers which renders adaptation of the parsing module necessary. See [issue 1](https://github.com/HBernigau/StackOverflowAnalysis/issues/1) for details and be a little patient for the second release... 😊 |


Download the repository and have a look on the documentation in *./docs/build/html/index.html*, 
especially the section on installation.

## Background

This software project was part of my MBA master thesis for my
[Executive MBA in Business and IT](https://www.lll.tum.de/executive-mba-in-business-it/), a joint  
program of the [Technical University of Munich (Germany)](https://www.tum.de/) and the [University of St. Gallen (Switzerland)](https://www.es.unisg.ch/en/university-st-gallen-hsg)
with an exchange module in [Tsinghua University, Beijing](https://www.tsinghua.edu.cn/en/).

Many thanks at this point to my Supervisor, [Prof. Barbara Weber](https://www.alexandria.unisg.ch/persons/8178),
chair of [Software Systems Programming and Development](https://ics.unisg.ch/chair-se-weber) of 
the University of St. Gallen!

My participation in that program was financed by my Employer, [d-fine GmbH](https://www.d-fine.com/),
what I am also very thankful for.

I am also very thankful to my *wife and to my nearly two years old son* for being very supportive in that rather 
stressful period of time consisting basically of working,
coding, fighting with the underlying technologies, 
reading articles and writing my Mater thesis...
