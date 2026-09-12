def friendly_error(exc):
    message = str(exc)

    if "kits_kit_id_key" in message:
        return (
            "This Kit ID already exists. "
            "Every kit must have a unique Kit ID. "
            "Please enter a different Kit ID."
        )

    if "unique_machine_run_per_day" in message:
        return (
            "This run number has already been recorded for "
            "this machine on this date. "
            "Please use the correct run number."
        )

    if "Daily summary not found" in message:
        return (
            "A Daily Summary has not been created for this date. "
            "Save the Daily Summary first, then record production."
        )

    if "Kit not found" in message:
        return (
            "The requested kit record could not be accessed. "
            "Please refresh the page and try again."
        )

    if "Only" in message and "runs remain" in message:
        return message.split("'message': '")[-1].split("'")[0]

    return f"Operation could not be completed: {message}"
