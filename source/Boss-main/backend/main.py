"""Main entry point – CLI commands for the recruitment system."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

# Ensure the backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

app = typer.Typer(
    name="boss-recruiter",
    help="Boss 直聘自动化招聘系统",
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    dev: bool = typer.Option(False, help="Development mode with auto-reload"),
) -> None:
    """Start the web server (API + frontend)."""
    from utils.logger import setup_logging
    setup_logging()

    console.print(f"[bold green]Starting server on http://{host}:{port}[/bold green]")
    console.print("Open in browser to access the recruitment dashboard.")

    uvicorn.run(
        "web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=dev,
        log_level="info",
    )


@app.command()
def setup() -> None:
    """Launch BOSS直聘 macOS app for initial login."""
    from utils.logger import setup_logging
    setup_logging()

    from rpa.chrome_connection import browser_mode
    from utils.config import get_config
    if browser_mode(get_config()):
        import webbrowser
        console.print('请在设置页检测已打开的 Chrome，或打开专用 Chrome 登录后接入。')
        webbrowser.open('http://127.0.0.1:8000/settings')
        return

    import subprocess

    boss_app = "/Applications/BOSS直聘.app"
    boss_exe = f"{boss_app}/Contents/MacOS/BOSS直聘"

    # Kill any existing BOSS instance
    subprocess.run(["pkill", "-9", "-f", "BOSS直聘"], capture_output=True)

    console.print("[bold]正在启动 BOSS直聘 桌面应用...[/bold]")
    console.print("[bold yellow]请在弹出的 BOSS直聘 APP 中登录你的招聘者账号[/bold yellow]")
    console.print("[bold yellow]登录成功后 APP 会自动保存登录状态[/bold yellow]\n")
    console.print("[bold yellow]保持 APP 在推荐牛人页面，然后回到这里按 Enter[/bold yellow]\n")

    # Launch with accessibility enabled
    subprocess.Popen(
        [boss_exe, "--force-renderer-accessibility"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    console.print("[green]BOSS直聘 APP 已启动![/green]")
    console.print("[bold yellow]登录完成后按 Enter 继续...[/bold yellow]")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass

    console.print("[bold green]完成! 登录状态已保存。现在可以启动自动化招聘了。[/bold green]")


@app.command()
def analyze(
    title: str = typer.Argument(..., help="Position title, e.g. 'Quant Trader'"),
    description: str = typer.Option("", help="Additional description"),
) -> None:
    """Analyze a position and generate JD + keywords."""
    from utils.logger import setup_logging
    setup_logging()

    from analyzer.position_analyzer import analyze_position

    console.print(f"[bold]Analyzing position: {title}[/bold]")

    analysis = analyze_position(title, description)

    console.print("\n[bold green]== Job Description ==[/bold green]")
    console.print(f"Title: {analysis.jd.title}")
    console.print(f"Summary: {analysis.jd.summary}")
    console.print(f"\nResponsibilities:")
    for r in analysis.jd.responsibilities:
        console.print(f"  - {r}")
    console.print(f"\nRequirements:")
    for r in analysis.jd.requirements:
        console.print(f"  - {r}")

    console.print("\n[bold green]== Keywords ==[/bold green]")
    console.print(f"Primary: {', '.join(analysis.keywords.primary_keywords)}")
    console.print(f"Skills: {', '.join(analysis.keywords.skill_keywords)}")
    console.print(f"Domain: {', '.join(analysis.keywords.domain_keywords)}")

    console.print("\n[bold green]== Filters ==[/bold green]")
    console.print(f"Min Experience: {analysis.filters.min_experience_years} years")
    console.print(f"Must-have Skills: {', '.join(analysis.filters.must_have_skills)}")


@app.command()
def status() -> None:
    """Show recruitment status overview."""
    from utils.logger import setup_logging
    setup_logging()

    from database.db import init_db, SessionLocal
    from database.models import Candidate, RecruitTask

    init_db()
    db = SessionLocal()

    tasks = db.query(RecruitTask).order_by(RecruitTask.created_at.desc()).limit(10).all()

    if not tasks:
        console.print("[yellow]No recruitment tasks found. Create one via the Web UI.[/yellow]")
        return

    table = Table(title="Recent Recruitment Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Position", style="green")
    table.add_column("Status", style="bold")
    table.add_column("Candidates", justify="right")
    table.add_column("Created", style="dim")

    for t in tasks:
        candidate_count = db.query(Candidate).filter(Candidate.task_id == t.id).count()
        table.add_row(
            str(t.id),
            t.position.title if t.position else "?",
            t.status,
            str(candidate_count),
            t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
        )

    console.print(table)
    db.close()


if __name__ == "__main__":
    app()
