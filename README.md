# atopile docs

Source for [https://docs.atopile.com](https://docs.atopile.com)

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
```

```bash
vale **
# or
vale my-file.mdx
```

### Upgrading styles:

```bash
vale lint
```
