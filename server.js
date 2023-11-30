const express = require('express');
const { MongoClient, ObjectId } = require('mongodb');

const dbUrl = 'mongodb://127.0.0.1:27017';

const app = express();
app.use(express.json());

app.use(cors());

const client = new MongoClient(dbUrl)
client.connect()

const products = client.db('db').collection('products')


app.get('/products', async (req, res) => {

  const query = {};
  let sortBy = "name"

  console.log(req.body);

  if (req.body.filter) {
    Object.keys(req.body.filter).forEach(key => {
      query[key] = req.body.filter[key]
    })

    sortBy = req.body.sortBy || sortBy;
  }

  try {
    const response = await products.find(query).sort(sortBy).toArray();
    res.json(response);
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
});


app.post('/products', async (req, res) => {

  const { name } = req.body;
  const query = { name: name }
  const product = await products.findOne(query);
  if (product) {
    res.status(400).send('Product with this name already exists');
    return;
  }

  try {
    const response = await products.insertOne(req.body);
    res.json(response);
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
});

app.put('/products/:id', async (req, res) => {

  const _id = new ObjectId(req.params.id);

  if (req.body._id) {
    delete req.body._id;
  }

  try {
    const response = await products.updateOne({ _id: _id }, { $set: req.body });
    res.json(response);
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
});

app.delete('/products/:id', async (req, res) => {

  const _id = new ObjectId(req.params.id);

  try {
    const response = await products.deleteOne({ _id: _id });
    res.json(response);
  } catch (error) {
    console.error(error);
    res.status(500).send('Internal Server Error');
  }
});


app.get('/products/raport/:name', async (req, res) => {

  const productName = req.params.name;

  try {
    // Agregacja dla raportu dla konkretnego produktu
    const report = await products.aggregate([
      {
        $match: {
          name: productName,
        },
      },
      {
        $project: {
          _id: 0,
          productName: '$name',
          quantity: '$quantity',
          totalValue: { $multiply: ['$price', '$quantity'] },
        },
      },
    ]).toArray();

    if (report.length === 0) {
      res.status(404).json({ error: 'Product not found' });
    } else {
      res.json(report); // Zwróć raport jako JSON
    }
  } catch (error) {
    console.error('Error generating report:', error);
    res.status(500).json({ error: 'Internal Server Error' });
  }
});



app.listen(3000, function () {
  console.log('Connected to mongodb');
});
