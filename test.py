import subprocess

def change_powershell_color():
    try:
        # Option 1: Change the console background (entire window)
        subprocess.run(
            ["pwsh", "-Command", "[Console]::BackgroundColor = 'Blue'; [Console]::ForegroundColor = 'Black'; Clear-Host"],
            check=True
        )

        # Option 2: Change PSReadLine background (input area only)
        # subprocess.run(
        #     ["pwsh", "-Command", "Set-PSReadLineOption -Colors @{ Background = 'DarkGreen' }"],
        #     check=True
        # )

        print("PowerShell color changed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Error executing PowerShell command: {e}")
    except FileNotFoundError:
        print("PowerShell not found in the container.")

if __name__ == "__main__":
    change_powershell_color()