# Introduction
Shekels is a local service which consumes a transactions CSV file downloaded
from mint.intuit.com. It conforms this data into a database, and displays it as
a searchable table and dashboard of configurable plots in web frontend.

See [documentation](https://thenewflesh.github.io/shekels/) for details.

# Installation
### Python
`pip install shekels`

### Docker
1. Install
   [docker](https://docs.docker.com/v17.09/engine/installation)
2. Install
   [docker-machine](https://docs.docker.com/machine/install-machine)
   (if running on macOS or Windows)
3. `docker pull thenewflesh/shekels:latest`

### Docker For Developers
1. Install
   [docker](https://docs.docker.com/v17.09/engine/installation)
2. Install
   [docker-machine](https://docs.docker.com/machine/install-machine)
   (if running on macOS or Windows)
3. Ensure docker-machine has at least 4 GB of memory allocated to it.
4. `git clone git@github.com:theNewFlesh/shekels.git`
5. `cd shekels`
6. `chmod +x bin/shekels`
7. `bin/shekels start`

The service should take a few minutes to start up.

Run `bin/shekels --help` for more help on the command line tool.
