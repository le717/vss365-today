from collections import namedtuple
from random import randrange

from flask import abort, flash, redirect, render_template, session, url_for
from num2words import num2words
from requests.exceptions import HTTPError

from src.blueprint import bp_root as root
from src.core import api
from src.core.filters import date as date_format
from src.core.forms import SubscribeForm, UnsubscribeForm


@root.route("form-subscribe", methods=["POST"])
def form_subscribe():
    form = SubscribeForm()
    # The magic "is human" numbers do not exist, don't continue on
    if "SUBSCRIBE_NUM" not in session or not form.validate_on_submit():
        flash("We were unable to add you to #vss365 notifications.", "error")
        return redirect(url_for("root.index"))

    # The magic numbers were not summed correctly
    if form.number.data != session["SUBSCRIBE_NUM"][0] + session["SUBSCRIBE_NUM"][1]:
        flash("We were unable to add you to #vss365 notifications.", "error")
        return redirect(url_for("root.index"))

    # Attempt to record the email
    email = form.email.data
    try:
        api.post("subscription/", params={"email": email})
        flash(
            f"{email} has been added to #vss365 notifications! Tomorrow's prompt will be in your inbox!",
            "info",
        )
    except HTTPError:
        flash(f"We were unable to add {email} to #vss365 notifications.", "error")
    return redirect(url_for("root.index"))


@root.route("subscribe")
def subscribe():
    # Generate two random numbers to use for a basic "is human" check.
    # Once generated, add them to the session for confirmation on form submit.
    # We generate these numbers on every page load unconditionally
    # so we don't persist anything
    second_num = randrange(16)
    random_nums = [randrange(1, 21), second_num, num2words(second_num)]
    session["SUBSCRIBE_NUM"] = random_nums

    # Build up the input label to contain the math equation to be solved
    # and remove any prior input the browser might have preserved (*@ Firefox...*)
    form = SubscribeForm()
    form.number.data = None
    form.number.label.text = f"{random_nums[0]} + {random_nums[2]} ="
    render_opts = {"form_subscribe": form}
    return render_template("root/subscribe.html", **render_opts)


@root.route("form-unsubscribe", methods=["POST"])
def form_unsubscribe():
    form = UnsubscribeForm()
    if not form.validate_on_submit():
        flash("We were unable to remove you from #vss365 notifications.", "error")
        return redirect(url_for("root.unsubscribe"))

    # Attempt to delete the email
    email = form.email.data
    try:
        api.delete("subscription/", params={"email": email})
        flash(f"{email} has been removed from #vss365 notifications.", "info")
        return redirect(url_for("root.index"))
    except HTTPError:
        flash(f"We were unable to remove {email} from #vss365 notifications.", "error")
        return redirect(url_for("root.unsubscribe"))


@root.route("unsubscribe", methods=["GET"])
def unsubscribe():
    render_opts = {"form_unsubscribe": UnsubscribeForm()}
    return render_template("root/unsubscribe.html", **render_opts)


@root.route("about")
def about():
    render_opts = {}
    return render_template("root/about.html", **render_opts)


@root.route("browse")
def browse():
    # Handle the archive file possibly being unavailable
    try:
        archive_name = api.get("archive")
    except HTTPError:
        archive_name = None

    render_opts = {
        "years": api.get("browse", "years"),
        "archive": archive_name,
    }
    return render_template("root/browse.html", **render_opts)


@root.route("browse/<year>")
def browse_by_year(year: str):
    # Get the host's list and group them up if needed
    try:
        prompt_months: list = api.get("browse", "months", params={"year": year})
    except HTTPError:
        abort(404)

    render_opts = {"months": prompt_months, "year": year}
    return render_template("root/browse-year.html", **render_opts)


@root.route("browse/<year>/<month>")
def browse_by_year_month(year: str, month: str) -> str:
    try:
        month_prompts: dict = api.get("browse", params={"year": year, "month": month})
    except HTTPError:
        abort(404)

    render_opts = {
        "date": date_format.format_month_year(f"{year}-{month}-01"),
        "month_prompts": month_prompts["prompts"],
    }
    return render_template("root/browse-month.html", **render_opts)


@root.route("donate")
def donate():
    Costs = namedtuple("Costs", ["cost", "month_freq"])
    site_costs = {
        "domain": Costs(8, 1),
        "email": Costs(10, 12),
        "server": Costs(4.5, 12),
    }
    render_opts = {"site_costs": site_costs}
    return render_template("root/donate.html", **render_opts)


@root.route("/")
def index():
    # Create a proper date object for each prompt
    # There are some older days that have multiple prompts,
    # and we need to handle these special cases
    available_prompts = api.get("prompt")
    prompts = []
    for prompt in available_prompts:
        prompt["date"] = date_format.create_datetime(prompt["date"])
        prompts.append(prompt)

    render_opts = {
        "prompts": prompts,
        "previous_day": prompts[0]["previous_day"],
        "next_day": None,
    }
    return render_template("root/tweet.html", **render_opts)


@root.route("view/<date>")
def view_date(date: str):
    # Try to get the prompt for this day
    try:
        available_prompts = api.get(
            "prompt", params={"date": date_format.create_datetime(date).isoformat()}
        )

    # There is no prompt for this day
    except HTTPError:
        abort(404)

    # Create a proper date object for each prompt
    # There are some older days that have multiple prompts,
    # and we need to handle these special cases
    prompts = []
    for prompt in available_prompts:
        prompt["date"] = date_format.create_datetime(prompt["date"])
        prompts.append(prompt)

    render_opts = {
        "prompts": prompts,
        "previous_day": prompts[0]["previous_day"],
        "next_day": prompts[0]["next_day"],
    }
    return render_template("root/tweet.html", **render_opts)
