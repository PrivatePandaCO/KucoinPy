# KucoinPy (KCW)
The stuff that speeds my crypto trading bots. My very own kucoin API wrapper in python, using sockets and conversing with the new HFT endpoints

### WIP Warning
It has quite a few issues as of now, especially with kucoin not responding to my pings - I don't know if this is my fault or kucoin's :( <br>
I know some of the works are bad, like return err instead of raise err - but this is still a pretty new wrapper, which was originally meant to be used only and only by me, for my pump trading bot. <br>
That said, I do believe this wrapper is pretty good for it's speed, and I'd appreciate any input and contributions to it.

---

<details>
    <summary> Features </summary>

- Socket cache
  - A new socket is used for each request.
  - This is done, in light of previous tests, to avoid buffer errors and closed socket errors.
- Websocket auto sub/re-sub
  - A pretty basic feature but one I really like
  - In the instance the websocket reboots, it automatically re-subscribes to old channels.
- Inbuilt subscriptions
  - By default, maintains balance and order history
- `second_message_handler`
  - Another very basic feature yet I'm very proud of, that is the ability to pass in a function to handle every websocket message after the default handler has ran.
  - This makes it useful to use in bots where you need additional manageemnt other than the inbuilt already implemented.
- `after_ws`
  - Similar to `second_message_handler`, it allows a function to be passed in that is called/ran after a websocket successfully boots.
  - This is useful in cases where the application requires extra work to be done after booting a socket before everything is ready
- `_shutdown_ws` object variable
  - Automatically varies from `True` to `False` based on the status of the websocket.
  - I found this really useful in HFT or even simply printing data; where it would print outdated data while the socket rebooted. Instead just check if this variable is `True` or `False`

</details>

<details>
    <summary> Installation </summary>

As easy as `pip install KucoinPy`

</details>

<details>
    <summary> Config </summary>

The variables to be passed in to `KCW()`<br>

- `kc_api_key, kc_api_secret, kc_api_passphrase,`: Self explanatory.
- `defaults`: Defaults to `None`
  - Default channels to subscribe to
  - Currently supports `/account/balance` and `/spotMarket/tradeOrdersV2`
  - Pass in `None` to not subscribe to any channels
  - Pass in a list of strings to subscribe to those channels
    - Format: `[("topic", private: bool), ("topic", private: bool)]`
    - Example: `[("/account/balance", True)]`
- `second_message_handler`: Defaults to doing nothing
  - Function called after default websocket message handler is ran.
  - Passes one parameter, message, which is the json of the websocket message.
- `after_ws`: Defaults to do nothing
  - Function called after websocket successfully boots.
  - Does not pass in any parameter
- `logger`: Defaults to `pyloggor(project_root="KucoinPy")`
  - A pyloggor object; check it out [here!](https://pypi.org/project/pyloggor/)
  - This is a library created by me for beautiful logging :)
  - Please note the default logger uses an option `project_root` which MAY slow down logging to about 0.0001 seconds or 0.1 ms for one log call. This occurs due to the stack depth being big.

</details>

<details>
    <summary> TODO </summary>

- I don't like the fact so much overhead is ran if only and only the websocket is required, probably something to be done on a later date.
- The recv function in the socket wrapper (`HTTP`), does not properly manage content length and often contains data which the `Response` class does not properly handle.
  - This happens when the response data is big and gets chunked, in which case the splitting and stuff doesn't resolve properly.
- Clean up log statements; really inconsistent and messy.
- Add support for the good stuff like transfers and order history and balance etc etc

</details>

---

## Appendix

Heyo, just your average good-for-nothing 16 year old backyard programmer here. Check [my site](https://privatepanda.co) instead :)<br>
If you liked this piece of work or it helped you in any way, buy me a coffee and make my day! [Support Me](https://privatepanda.co#patreon)
