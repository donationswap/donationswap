# Release Notes and Deployment steps.

## Maxwell's miscellaneous changes April-Jun 2020

- Changed the structure of the config file. Recaptcha site key is now included. This allows using a different recaptcha instance when developing locally.
  1. Before deployment, add `"captcha_site_key": "6LctxXUUAAAAAOcIxh6rm8KYTemy-zUIPspp-52P"` to `/srv/web/app-config.json`
- Separated watchdog email sender from donation swap email sender. Config file now needs additional parameters for this (to start with, they can be identical).
  1. Before deployment, add the keys `watchdog_email_password`, `watchdog_email_sender_name`, `watchdog_email_smtp`, and `watchdog_email_user` to `/srv/web/app-config.json` the config file with valid values (I suggest copying the donationswap config to start.)
