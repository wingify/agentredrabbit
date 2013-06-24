# agentredrabbit: Redis to RabbitMQ transport agent

agentredrabbit is a MIT licensed opinionated transport agent written in Python
which moves data from Redis to RabbitMQ. It uses multithreaded workers to do the
job and supports failsafe graceful shutdown.

## Naming conventions and assumptions

AMQP heartbeat is assumed at 100s.

AMQP exchange routing key string is of format: hostname.queuename.log

For every RabbitMQ queue name `q` that is to be transported, the corresponding Redis
list name is assumed as `queue:q\_redis`

World writes to Redis queue using RPUSH, we do LPUSH, LPOP, LTRIM, LRANGE etc.

## Building

Dependencies:

- pika
- redis (with hiredis for fast parsing)
- tests requires nose, unittest, mock

### Doc generation

To generate documentation of the code:

    $ make docs

This requires `epydoc` and will generate documentation in docs/agentredrabbit.

### Tests

To run unit tests:

    $ make runtests

### Installation

To install agentredrabbit, simply:

    $ make install

## Usage

Get help docs:

    $ agentredrabbit --help

Run with a configuration:

    $ agentredrabbit --config /path/to/conf.cfg

Example of running as a background process:

    $ agentredrabbit -c /path/to/cfg > agent.log 2> agent.log &

Process management using init.d script:

    $ /etc/init.d/agentredrabbit {start|stop|restart}

Gracefully stop running agent:

    $ kill -15 <pid of agentredrabbit>

## Contributing

Send a pull request on the [github repository](https://github.com/wingify/agentredrabbit).
