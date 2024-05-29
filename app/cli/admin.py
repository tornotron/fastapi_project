import sys
import os


# Ensure the app module is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import click
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.file_parser import parse_ticker_file
from app.db.crud.ticker import insert_single_ticker, ticker_exists, update_ticker
from app.db import crud


@click.group()
def cli():
    click.echo("Admin CLI")


@cli.command()
@click.option("--provider", help="The provider name.")
@click.option(
    "--file-path",
    type=click.Path(exists=True),
    required=True,
    help="The path to the CSV or Excel file.",
)
def bulk_upload_tickers(provider: str, file_path: str):
    db: Session = SessionLocal()
    try:
        file_type = file_path.split(".")[-1]
        if file_type not in ["csv", "xlsx"]:
            raise Exception("Unsupported file type")
        tickers_df = parse_ticker_file(file_path, file_type)
        crud.delete_tickers_by_provider(db, provider)
        crud.bulk_insert_tickers(db, tickers_df, provider)
        click.echo("Tickers uploaded successfully")
    except Exception as e:
        click.echo(f"Error: {str(e)}")
    finally:
        db.close()


@cli.command()
@click.option("--provider", required=True, help="The provider name.")
@click.option("--ticker", required=True, help="The ticker symbol.")
@click.option("--name", required=True, help="The name of the company.")
@click.option(
    "--exchange", required=True, help="The exchange where the ticker is listed."
)
@click.option("--category-name", required=True, help="The category name of the ticker.")
@click.option("--country", required=True, help="The country of the ticker.")
def upload_single_ticker(
    provider: str,
    ticker: str,
    name: str,
    exchange: str,
    category_name: str,
    country: str,
):
    db: Session = SessionLocal()
    try:
        ticker_row = {
            "ticker": ticker,
            "name": name,
            "exchange": exchange,
            "category_name": category_name,
            "country": country,
            "provider": provider,
        }

        if ticker_exists(db, ticker, provider):
            click.echo(f"Ticker {ticker} already exists for provider {provider}")
            return
        else:
            new_ticker = insert_single_ticker(db, ticker_row)
            click.echo(f"Ticker {new_ticker.ticker} uploaded successfully")
    except Exception as e:
        click.echo(f"Error: {str(e)}")
    finally:
        db.close()


@cli.command()
@click.option("--ticker", required=True, help="The ticker symbol.")
@click.option("--provider", required=True, help="The provider name.")
@click.option("--field", required=True, help="The field to update.")
@click.option("--value", required=True, help="The new value.")
def update_single_ticker(ticker: str, provider: str, field: str, value: str):
    db: Session = SessionLocal()
    try:
        updates = {field: value, "ticker": ticker, "provider": provider}
        ticker = update_ticker(db, updates)
        if ticker:
            click.echo(f"Ticker {ticker.ticker} updated successfully")
        else:
            click.echo("Ticker not found")
    except Exception as e:
        click.echo(f"Error: {str(e)}")
    finally:
        db.close()


@cli.command()
@click.option(
    "--file-path",
    type=click.Path(exists=True),
    required=True,
    help="Path to the CSV or Excel file containing tickers to update.",
)
def bulk_update_tickers(file_path: str):
    """Bulk update tickers in the database based on a given field."""
    db: Session = SessionLocal()
    try:
        file_type = file_path.split(".")[-1]
        if file_type not in ["csv", "xlsx"]:
            raise Exception("Unsupported file type")
        tickers_df = parse_ticker_file(file_path, file_type)
        crud.bulk_update_tickers(db, tickers_df)
        click.echo("Tickers updated successfully")
    except Exception as e:
        click.echo(f"Error: {str(e)}")
    finally:
        db.close()


if __name__ == "__main__":
    cli()