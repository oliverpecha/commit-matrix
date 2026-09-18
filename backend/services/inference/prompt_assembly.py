def build_prompt(arch_context, arch_gen_trail, hash_short, date_str, author, subject, diff):
    trail_section = f"\n\n# {arch_gen_trail}" if arch_gen_trail else ""
    return (
        f"# Repository Architecture Context\n{arch_context}{trail_section}\n\n"
        f"# Commit to Score\n"
        f"Hash: {hash_short}\n"
        f"Date: {date_str}\n"
        f"Author: {author}\n"
        f"Subject: {subject}\n\n"
        f"Diff:\n{diff[:8000]}\n"
    )
