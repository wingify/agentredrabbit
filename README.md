# agentredrabbit: Redis to RabbitMQ transport agent

agentredrabbit is a MIT licensed opinionated transport agent written in Python
which moves data from Redis to RabbitMQ. It uses multithreaded workers to do the
job and supports failsafe graceful shutdown.

## Naming conventions and assumptions

AMQP heartbeat is assumed at 100s.

AMQP exchange routing key string is of format: hostname.queuename.log

For every RabbitMQ queue name q we need to work on, the corresponding Redis
list name is assumed as "queue:q\_redis"

World writes to Redis queue using RPUSH, we do LPUSH, LPOP, LTRIM, LRANGE

## Installation

agentredrabbit dependencies:

- pika
- redis (with hiredis for fast parsing)
- watchdog
- tests requires nose, unittest, mock

To install agentredrabbit, simply:

    $ pip install agentredrabbit

## Usage

Get help docs:

    $ agentredrabbit --help

Run with a configuration:

    $ agentredrabbit --config /path/to/conf.cfg

Gracefully stop running agent:

    $ agentredrabbit --stop

Example of running as a background process:

    $ agentredrabbit -c /path/to/cfg > agent.log 2> agent.log &

## Contributing

Send a pull request on the [github repository](https://github.com/wingify/agentredrabbit).
