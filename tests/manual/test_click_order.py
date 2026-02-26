import click
from click.testing import CliRunner

def dec1(f):
    return click.option("--a")(f)

def dec2(f):
    return click.option("--b")(f)

def composite_reversed(f):
    f = dec2(f) # Applied FIRST -> INNER-MOST
    f = dec1(f) # Applied LAST  -> OUTER-MOST
    return f

@click.command()
@composite_reversed
def foo(b, a): # Testing if inner-most (dec2) is first
    click.echo(f"a={a}, b={b}")

if __name__ == "__main__":
    runner = CliRunner()
    result = runner.invoke(foo, ["--a", "1", "--b", "2"])
    print(result.output)
