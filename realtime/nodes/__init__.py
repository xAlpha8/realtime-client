import asyncio

from realtime.ops import merge


class Node:
    def __init__(self, *args, **kwargs):
        pass

    def run_task_in_loop(self):
        raise NotImplementedError("Subclasses must implement this method")


class SingleIONode(Node):
    """
    A basic node that can be used to create a node that has a single input and a single output.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run_task_in_loop(self):
        if self.inputs and len(self.inputs) > 1:
            raise ValueError("SingleIONode can only have one input")
        if self.outputs and len(self.outputs) > 1:
            raise ValueError("SingleIONode can only have one output")

        async def task():
            try:
                while True:
                    input_data = await self.inputs[0].get()
                    if asyncio.iscoroutinefunction(self.run):
                        output_data = await self.run(input_data)
                    else:
                        output_data = self.run(input_data)
                    await self.outputs[0].put(output_data)
            except Exception as e:
                print(f"Error in SingleIONode: {e}")
                raise e

        self._task = asyncio.create_task(task())

    def run(self, input_data):
        raise NotImplementedError("Subclasses must implement this method")


class MultipleIONode(Node):
    """
    A node that can have multiple inputs and outputs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run_task_in_loop(self):
        async def task():
            try:
                inputs = merge(self.inputs)
                while True:
                    input_data = await inputs.get()
                    if asyncio.iscoroutinefunction(self.run):
                        output_data = await self.run(input_data)
                    else:
                        output_data = self.run(input_data)
                    if output_data.output_stream is None:
                        raise ValueError("Output stream in output data is None")
                    for output in self.outputs:
                        if output.id == output_data.output_stream:
                            await output.put(output_data)
                            break
            except Exception as e:
                print(f"Error in MultipleIONode: {e}")
                raise e

        self._task = asyncio.create_task(task())

    def run(self, input_data):
        raise NotImplementedError("Subclasses must implement this method")
