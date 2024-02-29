# This program creates thumbnails of "png" and "tga" files which were recently
# added to Git repos. It loops through each repo folder (in the current folder),
# and creates a collage png of all recent images. Collages are created for each
# author and repo combination, and posted to a Discord channel.

import os
import sys
import git
import discord
import asyncio
import math
import json
from PIL import Image, UnidentifiedImageError, ImageOps
from datetime import datetime

# UPDATE this Discord Bot Token (found in the Discord Developer Portal->create application->bot user->token)
TOKEN = "ENTER-YOUR-DISCORD-BOT-TOKEN-HERE"

# List of recent SHA per repo
SHAS = {}

# Discord Colors
COLORS = [
    discord.Color.teal(),
    discord.Color.blue(),
    discord.Color.purple(),
    discord.Color.magenta(),
    discord.Color.gold(),
    discord.Color.orange(),
    discord.Color.brand_red(),
    discord.Color.dark_grey(),
    discord.Color.blurple(),
    discord.Color.fuchsia(),
    discord.Color.yellow(),
    discord.Color.pink(),
    discord.Color.light_embed(),
    discord.Color.dark_orange(),
    discord.Color.dark_magenta(),
    discord.Color.dark_purple(),
    discord.Color.green(),
]


def read_last_commit_shas(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

    
def save_last_commit_shas(file_path, last_commit_shas):
    with open(file_path, 'w') as file:
        json.dump(last_commit_shas, file, indent=4)


def get_modified_images(repo_name, repo_path, color, channel_id, last_sha):
    # Create a Git Repo object
    try:
        repo = git.Repo(repo_path)
    except git.exc.InvalidGitRepositoryError:
        print(f"{repo_path} is not a valid Git repo, skipping...")
        return

    # Get the commit log
    commit_log = repo.iter_commits()

    # List to store the rescaled image files
    extensions = (".png", ".tga")
    authors = {}
    hash = None

    # Loop through the commit log
    for commit in commit_log:
        if not hash:
            # Update most recent commit SHA
            hash = commit.hexsha
            SHAS[repo_name] = hash
            
        # Add author
        if commit.committer not in authors.keys():
            authors[commit.committer] = { "images": [], "messages": []}

        # Break the loop once previous SHA is found
        if commit.hexsha == last_sha:
            break
            
        # Skip any "Merge" commits
        if "merge" in commit.message.lower():
            continue

        # Access the diff of the commit
        modified_files = list(commit.stats.files.keys())

        # Check if the modified files have "png" or "tga" extension and are image files
        images = []
        for file in modified_files:
            file_path = os.path.join(repo_path, file)
            if file_path.endswith(extensions) and os.path.isfile(file_path):
                try:
                    img = Image.open(file_path).convert("RGBA")  # Convert to RGBA mode
                    img_resized = img.resize((256, 256), Image.NEAREST)  # Resize to 256x256 pixels
                    images.append(img_resized)
                except (IOError, OSError, UnidentifiedImageError) as e:
                    print(f"Error processing file '{file_path}': {e}")
                    
        # Add to author
        if images:
            authors[commit.committer]["images"].extend(images)
            authors[commit.committer]["messages"].extend(commit.message)

    # Group Discord messages By Author and Repo
    for author_name in authors.keys():
        author = authors[author_name]
        images = author["images"]
        messages = author["messages"]
        
        if not images:
            continue
            
        print(f" - {author_name}: found {len(images)} textures")

        # Define the border size
        border_size = 32

        # Calculate the grid size including borders
        grid_width = 6
        grid_height = min(math.ceil(len(images) / grid_width), 4)
        grid_length = grid_width * grid_height
        grid_size = (grid_width * (256 + border_size) + border_size, grid_height * (256 + border_size) + border_size)

        # Create a new blank RGBA image for the grid with an alpha channel
        grid_image = Image.new("RGBA", grid_size, (0, 0, 0, 0))

        # Paste the resized images onto the grid with borders
        for i, img in enumerate(images[:grid_length]):
            bordered_img = ImageOps.expand(img, border=border_size, fill=(0, 0, 0, 0))
            x = (i % grid_width) * (256 + border_size)
            y = (i // grid_width) * (256 + border_size)
            grid_image.paste(bordered_img, (x, y), mask=bordered_img)

        # Save the grid image
        output_path = "thumbnail.png"
        grid_image.save(output_path)

        # Call the function with the channel ID, message content, and image path
        image_path = "thumbnail.png"
        author = author_name
        title = os.path.basename(repo_path).upper()
        footer = f"{len(images)} Textures"

        # Post the Discord message
        asyncio.run(post_discord_message(channel_id, image_path, author, title, footer, color))
        

async def post_discord_message(channel_id, image_path, author, title, footer, color):
    # Define the necessary intents
    intents = discord.Intents.default()
    intents.typing = False
    intents.presences = False

    # Create a Discord client with the specified intents
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            # Find the specified channel
            channel = client.get_channel(channel_id)
            if channel is None:
                raise ValueError("Invalid channel ID")

            # Load the image and prepare the message
            file = discord.File(image_path, image_path)
            
            # Create embed for message
            embed = discord.Embed(color=color)
            embed.set_author(name=author)
            embed.title = title
            embed.set_footer(text=footer)
            embed.set_image(url=f"attachment://{image_path}")

            # Send the message with the image attachment
            await channel.send(file=file, embed=embed)
        except Exception as e:
            print(f"Error posting Discord message: {e}")

        # Close the Discord client
        await client.close()

    # Run the client with the provided token (i.e. your own `Discord Bot Token`)
    await client.start(TOKEN)

    
if __name__ == "__main__":
    print("---- thumbnail-bot.py ----")
    print(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    if len(sys.argv) != 2:
        print("Please provide the discord channel_id.")
        print("Example: python3 thumbnail-bot.py 907712334036930212")
        sys.exit(1)
    
    try:
        channel_id = int(sys.argv[1])
        current_dir = os.getcwd()
        
        # Read last SHA for each repo (to filter out previous commits)
        config_file = "thumbnail-commits.json"
        SHAS = read_last_commit_shas(config_file)

        # Loop through each Git repo in the parent folder
        for index, repo_name in enumerate(sorted(os.listdir(current_dir))):
            full_repo_path = os.path.join(current_dir, repo_name)
            if os.path.isdir(full_repo_path):
                last_sha = SHAS.get(repo_name, "N/A")
                color = COLORS[index % len(COLORS)]
                print(f"Repo: {full_repo_path}, Color: {color}, Last SHA: {last_sha}")
                
                # Find recent images pushed to Git
                get_modified_images(repo_name, full_repo_path, color, channel_id, last_sha)
        
        # Save the updated last commit SHA dictionary to the config file in JSON format
        save_last_commit_shas(config_file, SHAS)
        
    except ValueError:
        print("Invalid Discord Channel ID. Please provide a valid integer.")
        print("Example: python3 thumbnail-bot.py 907712334036930212")
        sys.exit(1)
