# atopile docs

Source for [https://docs.atopile.io](https://docs.atopile.io)

## Development

Previewing locally:

```bash
npm install -g mintlify
mintlify dev
```

## Linting

```bash
brew install vale
npm install -g mdx2vast

vale sync  # install styles
```

```bash
vale .
```


## Link checking

Internal links:
```bash
npm install -g mintlify
```

```bash
mintlify broken-links
```

External links:
```bash
brew install lychee
```

```bash
lychee .
```
