# agentredrabbit: Redis to RabbitMQ transport agent

agentredrabbit is a transport agent written in Python which moves data from
Redis to RabbitMQ. It uses multithreaded workers to do the job and supports
failsafe graceful shutdown.

## Naming conventions and assumptions

AMQP heartbeat is assumed at 100s.

AMQP exchange routing key string is of format: hostname.queuename.log

For every RabbitMQ queue named `q` that is to be transported, the corresponding
Redis list name is assumed as `queue:q`

Any service that is populating data in Redis should push in the corresponding
lists using RPUSH, `agentredrabbit` uses LPUSH, LPOP, LTRIM, LRANGE commands
internally.

## Building

Dependencies:

- pika
- redis (with hiredis for fast parsing)
- nose, mock (for tests)

### Doc generation

To generate documentation of the code:

    $ make docs

This requires `epydoc` and will generate documentation in docs/agentredrabbit.

### Tests

To run unit tests:

    $ make runtests

### Installation

To install agentredrabbit, simply:

    $ make build
    $ make install

## Usage

After installation, get help docs:

    $ agentredrabbit --help

Run with a configuration:

    $ agentredrabbit --config /path/to/conf.cfg

Example of running as a background process:

    $ agentredrabbit -c /path/to/cfg > agent.log 2> agent.log &

Process management using init.d script which is installed using `make install`:

    $ /etc/init.d/agentredrabbit {start|stop|restart}

Gracefully stop running agent:

    $ kill -15 <pid of agentredrabbit>

## Contributing

Send a pull request on the [github repository](https://github.com/wingify/agentredrabbit).
