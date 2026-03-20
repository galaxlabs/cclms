import frappe


def get_context(context):
    context.title = "Agent Command Centre"
    context.no_cache = 1
    context.page_title = "Agent Command Centre"
    return context
