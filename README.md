CryptoTax
=========

NOTE: This project now does more than just crypto tax stuff, so the README is outdated.

Do you need to file your taxes on crypto gains? Spoiler alert: It sucks.

This is an attempt to fill those tax forms for you automatically (or at least help you considerably) from exchange-exported trading data.

**NOTE:** This is a work in progress, not ready for use.

**NOTE:** This was primarily developed for use to file taxes in Sweden, which might lead to differences in how certain things are calculated or approached.

[![Build Status](https://travis-ci.org/ErikBjare/CryptoTax.svg?branch=master)](https://travis-ci.org/ErikBjare/CryptoTax)

## WILL CONTAIN BUGS, ALWAYS CHECK THE END RESULT MANUALLY


# Usage

Install dependencies using poetry: `poetry install`

Some commands require price history to function, you can download it by running: `make get_data`

Run in the poetry-managed virtualenv: `poetry run cryptotax`

# Resources

 - [Kryptovalutor](https://www.skatteverket.se/privat/skatter/vardepapper/andratillgangar/kryptovalutor.4.15532c7b1442f256bae11b60.html) (Skatteverket)
 - [Så beskattas kryptovalutor](https://www.kryptovalutor.se/sa-beskattas-kryptovalutor/) (kryptovalutor.se)
