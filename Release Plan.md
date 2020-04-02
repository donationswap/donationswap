# Release Notes and Deployment steps.

## Maxwell's miscellaneous changes April 2020

- Changed the structure of the config file. Recaptcha site key is now included. This allows using a different recaptcha instance when developing locally.
    1. Before deployment, add `"captcha_site_key": "6LctxXUUAAAAAOcIxh6rm8KYTemy-zUIPspp-52P"` to `/srv/web/app-config.json`
