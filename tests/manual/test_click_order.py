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
def foo(b, a):
    click.echo(f"a={a}, b={b}")

def test_click_option_order():
    runner = CliRunner()
    result = runner.invoke(foo, ["--help"])
    assert result.exit_code == 0
    # Click presents options in a deterministic order, independent of signature order.
    assert result.output.index("--a") < result.output.index("--b")
    assert [param.name for param in foo.params] == ["a", "b"]

    invoke = runner.invoke(foo, ["--a", "1", "--b", "2"])
    assert invoke.exit_code == 0
    assert "a=1, b=2" in invoke.output
