"""Contextual desktop guidance, keyed by the existing page titles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageGuide:
    steps: tuple[str, str, str]
    terms: tuple[str, str]
    tip: str


GUIDES: dict[str, PageGuide] = {
    "Process video": PageGuide(
        (
            "Choose a source video and a separate destination for the result.",
            "Start with Gentle, expand Test a short fragment, choose a sample "
            "and click Process sample.",
            "Compare before / after, listen to the sound, then start full processing.",
        ),
        (
            "Profile — a saved recipe for picture and sound changes.",
            "Encoder — how the result is compressed. Start with Automatic (recommended); "
            "parallel workers can increase speed and memory use.",
        ),
        "If the picture looks soft, try a gentler profile on the same sample first.",
    ),
    "Batch processing": PageGuide(
        (
            "Choose the folder containing your videos and a separate output folder.",
            "Select a profile and encoder that you have already checked on a sample.",
            "Run the batch and review the status and notes for each file.",
        ),
        (
            "One profile is applied to every video in the batch.",
            "Continue on error — process the remaining files if one fails.",
        ),
        "Test one representative video in Process video before processing the whole folder.",
    ),
    "Auto-tune": PageGuide(
        (
            "Choose a source video and a base profile to adjust.",
            "Keep the initial limits for your first search and click Calibrate.",
            "Review the result, save a tuned profile and test it in Process video.",
        ),
        (
            "Minimum quality — the measured picture-quality floor; higher is stricter.",
            "Maximum similarity — a local fingerprint limit. Iterations control "
            "the number of trials; longer samples take more time.",
        ),
        "Local scores do not predict platform decisions. Always watch and listen to a sample.",
    ),
    "Quality reports": PageGuide(
        (
            "Open an existing .qa.html report, or switch to Compute new.",
            "For a new report, select the matching source and processed video, "
            "then click Compute QA.",
            "Read the report here or open it in your browser; check the videos as well.",
        ),
        (
            "VMAF / SSIM — picture-quality estimates; higher usually means closer to the source.",
            "Similarity — how close local fingerprints are, not a quality rating.",
        ),
        "Numbers can miss blur, sound defects and sync problems; compare the actual clips.",
    ),
    "Profiles": PageGuide(
        (
            "Select an existing profile to see its transforms and settings.",
            "Change one setting at a time and check the YAML preview.",
            "Use Save as to create your own copy, then test it on a short sample.",
        ),
        (
            "Enabled — whether this transform is included in processing.",
            "Params (JSON) — transform settings. YAML preview — the complete profile recipe.",
        ),
        "For your first video, use a shipped profile; you can return to editing later.",
    ),
    "History": PageGuide(
        (
            "Use the filter to find a previous processing job.",
            "Open its output video or quality report from the Actions column.",
            "Check the recorded profile, encoder and status before comparing results.",
        ),
        (
            "Completed means processing finished; it does not replace a quality review.",
            "History records point to files on disk; moved or deleted files cannot be opened.",
        ),
        "Clear all removes history records, not your source or output videos.",
    ),
    "Reference library": PageGuide(
        (
            "Add a video that you own or are licensed to use as a local reference.",
            "Wait for its samples and fingerprints to be prepared, then refresh the list.",
            "Keep the references relevant to the comparisons you want to make.",
        ),
        (
            "Samples — short pieces used to describe the reference video.",
            "Audio FP — an audio fingerprint used for local similarity comparisons.",
        ),
        "You can process your first video without adding a reference library.",
    ),
    "Processing queue": PageGuide(
        (
            "Choose a queue folder and initialize it if this is a new queue.",
            "Add files, then select a profile, encoder and output folder in the worker tab.",
            "Start the worker and follow each file through the queue buckets.",
        ),
        (
            "Pending / leased / done / failed — waiting, assigned to a worker, "
            "completed or unsuccessful.",
            "Exit when queue empty — stop after current jobs; unchecked keeps waiting "
            "for new files.",
        ),
        "For a one-time folder of videos, Batch processing is the simpler starting point.",
    ),
    "Experiments": PageGuide(
        (
            "Choose an owned or licensed source, a profile and an output folder; "
            "generate a small number of variants.",
            "Move to the next step and record your observations with dates and notes.",
            "Save the CSV, then analyze the recorded observations in the final step.",
        ),
        (
            "Variant count — how many processed versions are generated for comparison.",
            "CSV — the saved observations table used by the analysis step.",
        ),
        "Use this section after sample review; local similarity alone cannot verify "
        "platform behavior.",
    ),
    "Settings": PageGuide(
        (
            "Choose your language and theme in Appearance.",
            "Set a default profile and history limits if needed.",
            "Click Save to keep the settings for your next session.",
        ),
        (
            "Default profile — the starting recipe for future processing sessions.",
            "Encoder cache — remembered hardware detection; reset it after changing "
            "hardware or drivers.",
        ),
        "Notifications and local telemetry are optional; leave them off for your first run.",
    ),
}
