#### v0.0.3b1
- Internal; Update send() function in http.py


#### v0.0.3
- Just push v0.0.2b1 to pypi as v0.0.3


#### v0.0.2b1
- Fix: `get_headers` function not returning headers, payload
- Update: Add traceback field to log statement in `get_balance` function


#### v0.0.2

- Fix: clientOid duplication in `multi_order`
- Fix: Incorrect variable access in `order`
- Update: Explicit for loop (3) left in the code for some reason, in `single_order` and `multi_order`
- Update: Rename `single_order` and `multi_order` to `_single_order` and `_multi_order` respectively to make it clear it's meant for internal use.
