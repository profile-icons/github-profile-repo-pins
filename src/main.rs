use clap::Parser;
use github_profile_repo_pins::{
    Result,
    app::Application,
    config::{Arguments, Config},
    github::GitHubClient,
};

fn run() -> Result<()> {
    let args: Arguments = Arguments::parse();
    let config: Config = Config::new(args)?;
    let github: GitHubClient = GitHubClient::new(
        &config.args.token,
        &config.args.graphql_url,
        &config.args.api_url,
    )?;
    Application::new(&github, config).run()?;
    Ok(())
}
fn main() -> std::process::ExitCode {
    match run() {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("repo-pins: {err:#}");
            std::process::ExitCode::FAILURE
        }
    }
}
