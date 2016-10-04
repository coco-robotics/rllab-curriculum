import tensorflow as tf
import numpy as np
from sandbox.rein.dynamics_models.utils import load_dataset_atari
import sandbox.rocky.tf.core.layers as L

# --
# Nonscientific printing of numpy arrays.
np.set_printoptions(suppress=True)
np.set_printoptions(precision=4)

bin_code_dim = 32


class IndependentSoftmaxLayer(L.Layer):
    def __init__(self, incoming, num_bins, W=L.XavierUniformInitializer(), b=tf.zeros_initializer,
                 **kwargs):
        super(IndependentSoftmaxLayer, self).__init__(incoming, **kwargs)

        self._num_bins = num_bins
        self.W = self.add_param(W, (self.input_shape[1], self._num_bins), name='W')
        self.b = self.add_param(b, (self._num_bins,), name='b')
        self.pixel_b = self.add_param(
            b,
            (self.input_shape[2], self.input_shape[3], self._num_bins,),
            name='pixel_b'
        )

    def get_output_for(self, input, **kwargs):
        fc = tf.matmul(
            tf.reshape(
                tf.transpose(
                    input, (0, 2, 3, 1)),
                tf.pack([tf.shape(input)[0], self.input_shape[1]])), self.W) + \
             self.b[np.newaxis, :]
        shp = self.get_output_shape_for([-1] + list(self.input_shape[1:]))
        fc_biased = fc.reshape(shp) + self.pixel_b
        out = tf.nn.softmax(
            fc_biased.reshape([-1, self._num_bins])
        )
        return out.reshape(shp)

    def get_output_shape_for(self, input_shape):
        return input_shape[0], input_shape[2], input_shape[3], self._num_bins


class DiscreteEmbeddingNonlinearityLayer(L.Layer):
    """
    Discrete embedding layer, the nonlinear part
    This has to be put after the batch norm layer.
    """

    def __init__(self, incoming, num_units,
                 **kwargs):
        super(DiscreteEmbeddingNonlinearityLayer, self).__init__(incoming, **kwargs)
        self.num_units = num_units

    def nonlinearity(self, x, noise_mask=1):
        # Force outputs to be binary through noise.
        return tf.nn.sigmoid(x) + noise_mask * tf.random_uniform(shape=tf.shape(x), minval=-0.3, maxval=0.3)

    def get_output_for(self, input, noise_mask=1, **kwargs):
        return self.nonlinearity(input, noise_mask)

    def get_output_shape_for(self, input_shape):
        return input_shape[0], self.num_units


class BinaryCodeConvAE:
    """Convolutional/Deconvolutional autoencoder with shared weights.
    """

    def __init__(self,
                 input_shape=(42, 42, 1),
                 ):
        self._x = tf.placeholder(tf.float32, shape=(None,) + input_shape, name="input")
        l_in = L.InputLayer(shape=(None,) + input_shape, input_var=self._x, name="input_layer")
        l_conv_1 = L.Conv2DLayer(
            l_in,
            num_filters=96,
            filter_size=5,
            stride=(2, 2),
            pad='VALID',
            nonlinearity=tf.nn.relu,
            name='enc_conv_1',
            weight_normalization=False,
        )
        l_conv_2 = L.Conv2DLayer(
            l_conv_1,
            num_filters=96,
            filter_size=5,
            stride=(2, 2),
            pad='VALID',
            nonlinearity=tf.nn.relu,
            name='enc_conv_2',
            weight_normalization=False,
        )
        l_flatten_1 = L.FlattenLayer(l_conv_2)
        l_dense_1 = L.DenseLayer(
            l_flatten_1,
            num_units=128,
            nonlinearity=tf.nn.relu,
            name='enc_hidden_1',
            W=L.XavierUniformInitializer(),
            b=tf.zeros_initializer,
            weight_normalization=False
        )
        l_code_prenoise = L.DenseLayer(
            l_dense_1,
            num_units=bin_code_dim,
            nonlinearity=tf.identity,
            name='binary_code_prenoise',
            W=L.XavierUniformInitializer(),
            b=tf.zeros_initializer,
            weight_normalization=False
        )
        l_code = DiscreteEmbeddingNonlinearityLayer(
            l_code_prenoise,
            num_units=bin_code_dim,
            name='binary_code',
        )
        l_dense_3 = L.DenseLayer(
            l_code,
            num_units=np.prod(l_conv_2.output_shape[1:]),
            nonlinearity=tf.nn.sigmoid,
            name='dec_hidden_1',
            W=L.XavierUniformInitializer(),
            b=tf.zeros_initializer,
            weight_normalization=False
        )
        l_reshp_1 = L.ReshapeLayer(
            l_dense_3,
            (-1,) + l_conv_2.output_shape[1:]
        )
        l_deconv_1 = L.TransposedConv2DLayer(
            l_reshp_1,
            num_filters=96,
            filter_size=5,
            stride=(2, 2),
            W=L.XavierUniformInitializer(),
            b=tf.zeros_initializer,
            crop='VALID',
            nonlinearity=tf.nn.relu,
            name='dec_deconv_1',
            weight_normalization=False,
        )
        l_deconv_2 = L.TransposedConv2DLayer(
            l_deconv_1,
            num_filters=1,
            filter_size=6,
            stride=(2, 2),
            W=L.XavierUniformInitializer(),
            b=tf.zeros_initializer,
            crop='VALID',
            nonlinearity=tf.nn.sigmoid,
            name='dec_deconv_2',
            weight_normalization=False,
        )
        # l_softmax = IndependentSoftmaxLayer(
        #     l_reshp_1,
        #     num_bins=64,
        # )
        # l_out = l_softmax
        l_out = l_deconv_2

        print(l_conv_1.output_shape)
        print(l_conv_2.output_shape)
        print(l_deconv_1.output_shape)
        print(l_deconv_2.output_shape)

        # --
        self._z = L.get_output(l_code, noise_mask=0)

        # --
        self._y = L.get_output(l_out, deterministic=True)

        # --
        self._z_in = tf.placeholder(tf.float32, shape=(None, bin_code_dim), name="input")
        self._y_gen = L.get_output(l_out, {l_code: self._z_in}, deterministic=True)

        # --
        self._cost = tf.reduce_sum(tf.square(L.get_output(l_out) - self._x))

        # --
        learning_rate = 0.001
        self._optimizer = tf.train.AdamOptimizer(learning_rate).minimize(self._cost)

    def transform(self, sess, X):
        """Transform data by mapping it into the latent space."""
        # Note: This maps to mean of distribution, we could alternatively
        # sample from Gaussian distribution
        return sess.run(self.z, feed_dict={self.x: X})

    def generate(self, sess, z=None):
        """ Generate data by sampling from latent space.

        If z_mu is not None, data for this point in latent space is
        generated. Otherwise, z_mu is drawn from prior in latent
        space.
        """
        if z is None:
            z = np.random.randint(0, 2, (1, bin_code_dim))
        # Note: This maps to mean of distribution, we could alternatively
        # sample from Gaussian distribution
        return sess.run(self._y_gen, feed_dict={self._z_in: z})

    def reconstruct(self, X):
        """ Use VAE to reconstruct given data. """
        return self.sess.run(self.y, feed_dict={self.x: X})

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def z(self):
        return self._z

    @property
    def cost(self):
        return self._cost

    @property
    def optimizer(self):
        return self._optimizer

    @property
    def n_classes(self):
        return self._n_classes


def test_atari():
    import matplotlib.pyplot as plt

    atari_dataset = load_dataset_atari('/Users/rein/programming/datasets/dataset_42x42.pkl')
    atari_dataset['x'] = atari_dataset['x'].transpose((0, 2, 3, 1))
    ae = BinaryCodeConvAE()

    sess = tf.Session()
    sess.run(tf.initialize_all_variables())

    n_epochs = 5
    for epoch_i in range(n_epochs):
        train = atari_dataset['x']
        sess.run(ae.optimizer, feed_dict={ae.x: train})
        print(epoch_i, sess.run(ae.cost, feed_dict={ae.x: train}))

    n_examples = 10
    examples = np.tile(atari_dataset['x'][0][None, :], (n_examples, 1, 1, 1))
    # examples = atari_dataset['x'][0:n_examples]

    recon = sess.run(ae.y, feed_dict={ae.x: examples})
    fig, axs = plt.subplots(2, n_examples, figsize=(20, 4))
    for example_i in range(n_examples):
        axs[0][example_i].imshow(
            np.reshape(atari_dataset['x'][example_i], (42, 42)),
            cmap='Greys_r', vmin=0, vmax=1, interpolation='none')
        axs[0][example_i].xaxis.set_visible(False)
        axs[0][example_i].yaxis.set_visible(False)
        axs[1][example_i].imshow(
            np.reshape(recon[example_i], (42, 42)),
            cmap='Greys_r', vmin=0, vmax=1, interpolation='none')
        axs[1][example_i].xaxis.set_visible(False)
        axs[1][example_i].yaxis.set_visible(False)

    fig.show()
    plt.show()

    recon = ae.generate(sess, np.random.randint(0, 2, (n_examples, bin_code_dim)))
    fig, axs = plt.subplots(2, n_examples, figsize=(20, 4))
    for example_i in range(n_examples):
        axs[0][example_i].imshow(
            np.reshape(atari_dataset['x'][example_i], (42, 42)),
            cmap='Greys_r', vmin=0, vmax=1, interpolation='none')
        axs[0][example_i].xaxis.set_visible(False)
        axs[0][example_i].yaxis.set_visible(False)
        axs[1][example_i].imshow(
            np.reshape(recon[example_i], (42, 42)),
            cmap='Greys_r', vmin=0, vmax=1, interpolation='none')
        axs[1][example_i].xaxis.set_visible(False)
        axs[1][example_i].yaxis.set_visible(False)

    tf.train.SummaryWriter('/Users/rein/programming/tensorboard/logs', sess.graph)
    fig.show()
    plt.show()


if __name__ == '__main__':
    test_atari()
