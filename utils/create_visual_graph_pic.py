from utils.abs_path import abs_path


def create_visual_graph_pic(workflow, file_name):
    img = workflow.get_graph().draw_mermaid_png()
    img_path = abs_path(f"../asset/graph/{file_name}.png")
    with open(img_path, "wb") as f:
        f.write(img)
